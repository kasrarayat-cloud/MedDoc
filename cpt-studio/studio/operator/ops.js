'use strict';
// CPT Studio OPERATOR CONSOLE (CORE-UX-DESIGN.md 5): a copy of the website's studio/static/studio/app.js as it
// stood at c9f20a148, with its API base switched to /ops/api/ and the trace link shown in the console. Served only
// to platform operators by studio.operator.script (never from static/); its tests are tests/operator/ops.test.cjs.
// CPT Studio frontend over the JSON API in API.md. Rendering builds markup
// strings in the approved design's shape; every server value passes through
// escapeHtml. Helpers above the DOM section are pure and unit-tested under node.

const POLL_BASE_MS = 2500;
const POLL_MAX_MS = 15000;
const POLL_MAX_ERROR_MS = 30000;
const MAX_UPLOAD_BYTES = 15 * 1024 * 1024;
const MAX_PASTE_CHARS = 400000;
const MAX_ADDENDUM_CHARS = 20000;
const MIN_RECONCILE_CHARS = 12;
const UPLOAD_NAME = /\.(pdf|docx|txt)$/i;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
// Every page of the console is an operator's (studio.operator.operator_view): the trace link is shown on each.
const OPERATOR_CONSOLE = true;
const REPORT_URL = /^\/ops\/api\/reports\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\/download$/i;
const PARAGRAPH_BREAK = /\n(?:[^\S\n]*\n)+/g;
// States that wait on a member: a clarification, a review decision, or a reconciliation. The queue of a list row served
// without queue_reasons (inQueue).
const QUEUE_STATES = new Set(['needs_clarification', 'ready_for_review', 'provider_unknown']);
// What a queued row waits on a member for (queue_reasons, served from the rows), as its meta line says it. 'question' is
// already the row's open-question count, and 'state' its badge.
const QUEUE_REASON_LABELS = { decision: 'Decision needed', reconciliation: 'Provider outcome to reconcile', incomplete: 'Coding incomplete', second_review: 'Second review available' };
const EXCERPT_POINTS = 80;
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const NUMBER_WORDS = ['No', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten'];
const HTML_ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;', '`': '&#x60;' };

const SETTING_LABELS = { office: 'Office', hospital_outpatient: 'Hospital outpatient department', asc: 'Ambulatory surgery center', inpatient: 'Inpatient', emergency: 'Emergency department', telehealth: 'Telehealth' };
const BILLING_LABELS = { professional: 'Professional', facility: 'Facility' };
const PATIENT_LABELS = { new: 'New patient', established: 'Established patient' };
const SOURCE_KINDS = { pdf: 'PDF', docx: 'DOCX', txt: 'TXT', paste: 'Pasted text', addendum: 'Addendum' };
const METHOD_LABELS = { txt: 'Text file', docx: 'Word document', 'pdf-text': 'PDF text layer', 'pdf-ocr': 'PDF read with OCR', 'pdf-mixed': 'PDF text layer and OCR', paste: 'Pasted text', addendum: 'Text with addendum' };
const STATE_TONES = { ready_for_review: 'green', reviewed: 'green', needs_clarification: 'amber', provider_unknown: 'amber', provider_failed: 'amber', extraction_failed: 'amber' };
const STAGES = [['extract', 'Read the original document'], ['analyze', 'Identify documented services and context'], ['predict', 'Corti: request CPT proposals'], ['astra', 'Independent review: Astra (OpenAI GPT-6 Astra)'], ['fable', 'Independent review: Fable (Anthropic Claude Fable 5.1)'], ['assess', 'Check proposals against references and reconcile']];
// Astra's and Fable's own stages (HARNESS.md 2): a row once the stage exists or the API's harness lists the participant.
const PARTICIPANT_STAGES = new Set(['astra', 'fable']);
const SECOND_REVIEW_STAGE = ['review2', 'Second provider review (asked for by a reviewer)'];
// harness@2 (HARNESS.md 11.1, 12.1): once every first reading is frozen and the first assessment made, each
// participant's peer review, then the second (final) assessment. Their rows appear once the API reports a participant
// phase.
const PEER_STAGES = [['astra_peer', 'Peer review: Astra (OpenAI GPT-6 Astra)'], ['fable_peer', 'Peer review: Fable (Anthropic Claude Fable 5.1)']];
const PEER_KINDS = new Set(PEER_STAGES.map(([kind]) => kind));
const FIRST_ASSESS_LABEL = 'First assessment: check the frozen first readings against references';
const SECOND_ASSESS_STAGE = ['assess2', 'Second assessment: reconcile both phases (final)'];
// The Gemini migration (cpt-studio/design: FINAL.md 3.2, 6.3-6.4, 8.3, 11): the interpret stage reads the document into
// an event inventory through Gemini, and analyze then derives the context from that inventory, reading nothing. Their rows
// are drawn so only where an interpret stage exists: an earlier encounter's card is drawn as before.
const INTERPRET_STAGE = ['interpret', 'Gemini: read the documented procedures into an event inventory'];
const DERIVE_STAGE_LABEL = 'Derive the context from the event inventory';
// The stages that start a chain or read the document afresh: an assess after one of them, with no peer stage between,
// is a first assessment (phasedJobs).
const CHAIN_KINDS = new Set(['extract', 'interpret', 'analyze', 'predict', 'astra', 'fable']);
const STAGE_STATES = { queued: 'Waiting', running: 'In progress', succeeded: 'Done', failed: 'Failed', unknown: 'Outcome unknown', cancelled: 'Stopped' };
const STAGE_LOOKS = { queued: ['muted', 'clock'], running: ['pending running', 'clock'], succeeded: ['', 'circle-check'], failed: ['pending', 'close'], unknown: ['pending', 'info'], cancelled: ['muted', 'stop'] };
// The harness participants (HARNESS.md 1), keyed as the API names them in harness.participants, proposed_by,
// participant_positions and the provider runs.
const PARTICIPANT_TITLES = { corti: 'Corti (Corti coding tool)', astra: 'Astra (OpenAI GPT-6 Astra)', fable: 'Fable (Anthropic Claude Fable 5.1)' };
const PARTICIPANT_LABELS = { corti: 'Corti', astra: 'Astra', fable: 'Fable' };
// How a participant stands on this revision (harness.participants[].state): the row's look, from the progress card's
// own STAGE_LOOKS, its short label, the plain sentence said when the API gives none, and - for a state that must be
// said plainly - the words the API's own sentence has to contain for the plain one to be left out.
const PARTICIPANT_STATES = {
  not_configured: [['muted', 'info'], 'Not configured', 'Not configured on this installation.', 'not configured'],
  waiting: [STAGE_LOOKS.queued, 'Waiting', 'Waiting for its turn; nothing has been sent yet.'],
  running: [STAGE_LOOKS.running, 'In progress', 'Reading the document now.'],
  done: [STAGE_LOOKS.succeeded, 'Done', 'Answered, and the answer was read.'],
  refused: [STAGE_LOOKS.unknown, 'Reading not used', 'Answered; the reading was not used.', 'not used'],
  failed: [STAGE_LOOKS.failed, 'Failed', 'The request failed and is not sent again for this revision; an addendum makes a new request.', 'not sent again'],
  unknown: [STAGE_LOOKS.unknown, 'Outcome unknown', 'Outcome unknown — reconcile before sending again.', 'reconcile'],
  not_sent: [['muted', 'info'], 'Not sent', 'Nothing was sent.'],
  blocked: [['pending', 'clock'], 'Blocked', 'Not sent: an unknown outcome must be reconciled before anything is sent again.', 'reconcile'],
  stopped: [STAGE_LOOKS.cancelled, 'Stopped', 'Stopped; nothing was sent for it.'],
};
// A participant's peer review (harness.participants[].peer, HARNESS.md 11.1, 12.6), as PARTICIPANT_STATES words a first
// reading: the row's look, its label, the plain sentence and the words the API's own sentence must contain for the
// plain one to be left out. not_run is the page's own, where the API serves no peer review: it says only what is true
// of the assessment shown - the revision can hold peer-review runs that assessment did not read (refutation round 2,
// truth-9: it read "No peer review is recorded for this revision" beside them).
const PEER_STATES = {
  waiting: [STAGE_LOOKS.queued, 'Waiting', 'Waiting: the peer reviews start once every first reading is frozen and the first assessment is made.'],
  running: [STAGE_LOOKS.running, 'In progress', 'Reviewing its peers\' frozen conclusions now.'],
  stopped: [STAGE_LOOKS.cancelled, 'Stopped', 'Stopped before its peer review finished; Resume runs it.', 'stopped'],
  done: [STAGE_LOOKS.succeeded, 'Done', 'Answered in peer review, after its first reading was frozen; the review was used.'],
  refused: [STAGE_LOOKS.unknown, 'Review not used', 'Answered in peer review; the review was not used.', 'not used'],
  failed: [STAGE_LOOKS.failed, 'Failed', 'The peer-review request failed and is not sent again for this revision.', 'failed'],
  unknown: [STAGE_LOOKS.unknown, 'Outcome unknown', 'Outcome unknown — reconcile before anything is sent again.', 'reconcile'],
  not_sent: [['muted', 'info'], 'Not run', 'No peer review was sent.'],
  blocked: [['pending', 'clock'], 'Blocked', 'Not sent: an unknown outcome must be reconciled before anything is sent again.', 'reconcile'],
  not_configured: [['muted', 'info'], 'Not configured', 'Not configured on this installation.', 'not configured'],
  not_run: [['muted', 'info'], 'Not run', 'No peer review was read by this assessment.'],
};
// Why a participant whose first reading was not used takes no part in peer review (HARNESS.md 11.1).
const PEER_NOT_RUN = 'Not run: only a participant whose own first reading was used takes part in peer review, so this one never sees its peers\' conclusions.';
// Reference validation (harness.reference_validation, HARNESS.md 5): its look, label and plain sentence by state, and -
// for 'failed' and 'not_verified', which must be said plainly - the words the API's own sentence (its detail) has to
// contain for the plain one to be left out. A retrieval that failed is shown as failed, never as not run or done
// (refutation round 1, parity-1); one no installed CMS reference file applied to checked no code, and says so, never
// done (refutation round 2, truth-3). The plain sentence for a failure is said of any assessment, so it claims neither
// that the codes' checks read the CMS facts nor that none was checked: the API's own sentence says which (refutation
// round 3, truth-1).
const REFERENCE_STATES = {
  waiting: [STAGE_LOOKS.queued, 'Waiting', 'Runs once the participants have answered: every proposed code is looked up in the connected CMS reference files.'],
  done: [STAGE_LOOKS.succeeded, 'Done', ''],
  not_verified: [STAGE_LOOKS.unknown, 'Not verified', 'No code was checked against the CMS reference files: no installed CMS reference file applies to the service date.', 'no code was checked'],
  failed: [STAGE_LOOKS.failed, 'Failed', 'Reference validation failed: CPT Studio\'s retrieval for this assessment\'s codes failed, so no CMS reference fact or passage is listed here; each code\'s CMS reference checks stand as its status line shows them.', 'failed'],
  not_run: [['muted', 'info'], 'Not run', 'No proposal was checked against the CMS references for this revision.'],
};
// What a code card says where the assessment's retrieval failed (harness.reference_validation 'failed'): no CMS
// reference fact or passage is listed for any code - never to be read as a lookup that found nothing for this one - and
// the code's CMS reference checks stand as its status line shows them (refutation round 2, truth-4). Said of every
// card, so it claims neither that the checks read the CMS facts - where no CMS reference file applied to the service
// date none did, and each reads "not verified" - nor that none did: the Reference validation row's own sentence says
// which (refutation round 3, truth-1).
const RETRIEVAL_FAILED = 'Reference validation failed for this assessment, so no CMS reference fact or passage is listed for this code. Its CMS reference checks stand as its status line shows them; the Reference validation row says what failed.';
// A code's three statuses (HARNESS.md I4): proposed (by whom), reference-checked and approved, never one merged state.
const REFERENCE_CHECK_LABELS = { passed: 'passed', attention: 'needs attention', not_verified: 'not verified' };
const POSITION_WORDS = { proposed: 'proposed it', not_proposed: 'did not propose it', advised_not_to_code: 'advised not to code it', not_run: 'gave no reading' };
const DECISION_WORDS = { approved: 'approved{by}', rejected: 'rejected{by}', reinstated: 'reinstated for review{by}; not approved', exclusion_confirmed: 'exclusion confirmed{by}', undecided: 'not decided yet' };
const NOT_CODED_WORDS = { not_performed_at_this_encounter: 'not performed at this encounter', included_in_another_code: 'included in another code', insufficient_documentation: 'insufficient documentation', outside_gi_scope: 'outside the GI scope', other: 'another reason' };
const RUN_PROVIDERS = { corti: 'Corti', replay: 'Replay', astra: 'Astra', fable: 'Fable', gemini: 'Gemini' };
const RUN_PURPOSES = { primary: 'Primary request', second_review: 'Second review', independent: 'Independent review', peer_review: 'Peer review', interpretation: 'Interpretation' };
// The runs the Activity tab names by purpose; a primary request reads as before.
const NAMED_PURPOSES = new Set(['second_review', 'independent', 'peer_review', 'interpretation']);
// The interpreter's runs (purpose interpretation): Gemini reading the documented procedures (FINAL 6.3).
const INTERPRETER_TITLE = 'Gemini, the interpreter';
// harness@2's words (HARNESS.md 11.1-11.4, 12.5): the phase a participant proposed a code or located a passage in, a
// peer-review position, an assessment's phase, and the facts a reviewer confirms - the engine's own labels.
const PROPOSED_PHASES = { independent: 'independent reading', peer_review: 'after peer review' };
const LOCATED_PHASES = { independent: 'in its independent first reading', peer_review: 'in peer review' };
const PEER_POSITIONS = { supports: 'supports it', disputes: 'disputes it', cannot_tell: 'cannot tell' };
const ASSESSMENT_PHASES = { 0: 'No model participant: Corti only', 1: 'Phase 1: the frozen first readings', 2: 'Phase 2: after peer review' };
// The facts a new-path code asks about (FINAL 7.4, 8.3; answers.PROMPTS and interpretation.wording.MISSING), in the
// console's words: each names what CPT Studio could not confirm of one act, never that the document leaves it out.
const EVENT_FACTS = {
  event_time: 'Done at this encounter, on the date of service', event_performer: 'Who performed the act',
  act_target: 'The lesion or site the act was done on', technique: 'The technique used',
  statement_scope: 'Whether a statement applies to the act', act_method: 'The method the lesion was removed by',
  procedure: 'The procedure the act was done in',
};
const FINDING_FACTS = { service_date: 'Date of service', performed_status: 'Performed at this encounter', extent: 'Extent reached', target: 'Structure examined', cannulation: 'Cannulation outcome', em_basis: 'Basis for the visit level (total time or medical decision making)', ...EVENT_FACTS };
// An event's attributes in the order the interpretation section lists them (the contract's 4.2 record), each with its
// label; a value's underscores are read as spaces.
const EVENT_ATTRIBUTES = [['procedure', 'Procedure'], ['kind', 'Act'], ['status', 'Status'], ['time', 'Time'], ['performer', 'Performer'],
  ['target', 'Target'], ['technique', 'Technique'], ['scope', 'Scope'], ['purpose', 'Purpose'], ['extent', 'Extent'], ['completion', 'Completion'],
  ['part_of', 'Part of'], ['sequence', 'Sequence']];
const ATTRIBUTE_STATES = { verified: 'verified', unverified: 'unverified', absent: 'absent', discarded: 'discarded' };
const BASES = { stated: 'stated', default: 'the frame default', absent: 'not given' };
const INTERPRETATION_TAB = ['interpretation', 'Interpretation'];
const RETRY_DONE = 'The reading is tried once more, as a stage of its own; the release of the failed attempt is recorded.';
const HOLD_RELEASED = 'The interpreter hold was released and the release recorded. Members can now resume the documents it paused.';
const CANDIDATE_NOTE = 'A candidate answers nothing until a reviewer confirms it. Agreement between participants never verifies or confirms one, and a confirmation approves no code.';
// What a verified candidate's consistency check established, by fact (HARNESS.md 12.5, as refutation round 2 left it):
// every fact's passage lies in no history, plan or indication section (VERIFIED_SECTIONS), and a status is read by CPT
// Studio's readers on the act the code accounts for, in the passage's whole sentence (EV2-1, EV2-2, EV2-3, truth-1).
const VERIFIED_SECTIONS = 'in no history, plan or indication section';
const VERIFIED_CHECKS = {
  service_date: 'it states that calendar date, which CPT Studio\'s readers do not read as a date of birth',
  extent: 'it names that landmark, which CPT Studio\'s readers read neither as not reached nor as qualified (a negation, an attempt or a doubt)',
  target: 'it names that structure, which CPT Studio\'s readers read neither as not seen nor as qualified (a negation, an attempt or a doubt)',
  cannulation: 'it states that cannulation outcome',
  performed_status: 'CPT Studio\'s readers read its whole sentence as stating that status for the act this code accounts for (for a code of the whole service, for that service)',
  em_basis: 'it states a total time in minutes or a level of medical decision making',
};
// Free text a participant wrote (a basis, a description, a quote it could not locate) that reads like a CPT descriptor -
// the AMA's plural marks ("polyp(s)"), "; with", "single or multiple", "when performed", "(separate procedure)", "list
// separately"; the office E/M long descriptor's frame ("visit for the ... of a new patient", "medically appropriate
// history", "minutes must be met or exceeded"); and an abbreviated short descriptor's "W/", "W/O", "SINGLE/MULTIPLE"
// (refutation round 2, IR2-4) - is withheld, never shown (HARNESS.md I9): no licensed descriptor is connected, and a
// model can write one. The document's own text and the retrieved CMS passages are shown as they are.
const DESCRIPTOR_LIKE = /\((?:s|es|ies)\)|;\s*(?:with|without|diagnostic|including|each|single|multiple|first|initial)\b|\bsingle or multiple\b|\bwhen performed\b|\(separate procedure\)|\blist separately\b|\bvisit for the\b[^.;]{0,80}?\bof an? (?:new|established) patient\b|\bmedically appropriate history\b|\bminutes must be met or exceeded\b|\bsingle\/multiple\b|\bw\/(?:o\b|[a-z])/i;
const DESCRIPTOR_WITHHELD = 'Withheld: this text reads like a CPT descriptor, which CPT Studio never shows.';
const CHECK_LABELS = { pass: 'Pass', warn: 'Warning', fail: 'Fail', not_verified: 'Not verified', not_applicable: 'Not applicable', info: 'Information' };
const CHECK_LOOKS = { pass: ['', 'circle-check'], info: ['muted', 'info'], not_applicable: ['muted', 'info'], warn: ['pending', 'info'], fail: ['pending', 'close'], not_verified: ['pending', 'clock'] };
const RUN_STATES = { reserved: 'Reserved', sending: 'Sending', succeeded: 'Succeeded', failed: 'Failed', unknown: 'Outcome unknown', not_sent: 'Not sent', cancelled: 'Cancelled' };
const DECISION_TITLES = { approve: 'Approved', reject: 'Rejected', reinstate: 'Reinstated for review', confirm: 'Exclusion confirmed', revoke: 'Revoked the decision on' };
const ACTION_BUTTONS = [['approve', 'primary', 'Approve', 'check'], ['reject', 'secondary', 'Reject', ''], ['reinstate', 'secondary', 'Reinstate for review', ''], ['confirm', 'secondary', 'Confirm exclusion', ''], ['revoke', 'secondary', 'Undo decision', '']];
const TABS = [['codes', 'Suggestions'], ['checks', 'Checks'], ['timeline', 'Activity']];
const ROUTE_TITLES = { workspace: 'Overview', documents: 'Documents', queue: 'Review queue', 'how-it-works': 'How it works', doc: 'Document review', trace: 'Document trace' };
// The owner's trace of one document (HARNESS.md 7): #/encounters/<id>/trace.
const TRACE_ROUTE = /^\/encounters\/([^/]+)\/trace$/;
const ACKNOWLEDGEMENTS = {
  human: 'I read the whole source document, not only the cited passages, and it supports this code as a service performed at this encounter. The documentation checks can miss wording they do not recognise. This synthetic review is not clinical approval or billing advice.',
  agent: 'I am an automated agent. I read the whole source document, not only the cited passages, and it supports this code as a service performed at this encounter. The documentation checks can miss wording they do not recognise. This agent-executed synthetic review is not clinical approval or billing advice.',
};
// The attestation the server accepts is the one /ops/api/session serves (round 5, bypass:4); the built-in copy above
// only covers a page drawn before the session loads, and tests hold the two equal.
function attestationText(session) {
  return session?.acknowledgement || (session?.user?.actor_kind === 'agent' ? ACKNOWLEDGEMENTS.agent : ACKNOWLEDGEMENTS.human);
}
const REVIEW_COPY = {
  approve: { eyebrow: 'APPROVE', title: 'Make the decision visible.', button: 'Approve code' },
  reject: { eyebrow: 'REJECT', title: 'Leave a clear record.', button: 'Reject code' },
  reinstate: { eyebrow: 'REINSTATE', title: 'Bring it back for review.', button: 'Reinstate for review' },
  confirm: { eyebrow: 'CONFIRM EXCLUSION', title: 'Agree with the check, on the record.', button: 'Confirm exclusion' },
};

// --- pure helpers ----------------------------------------------------------------

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"'`]/g, ch => HTML_ESCAPES[ch]);
}

function lookup(map, key, fallback) {
  return typeof key === 'string' && Object.hasOwn(map, key) ? map[key] : fallback;
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

function passagesLabel(count) {
  return `${NUMBER_WORDS[count] || count} ${count === 1 ? 'passage' : 'passages'} linked to this suggestion`;
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

function pollDelay(count, errors) {
  if (errors > 0) return Math.min(POLL_MAX_ERROR_MS, POLL_BASE_MS * 2 ** errors);
  return Math.min(POLL_MAX_MS, Math.round(POLL_BASE_MS * 1.25 ** count));
}

function parseRoute(hash) {
  const path = String(hash || '').replace(/^#/, '');
  if (path.startsWith('doc/')) return { name: 'doc', id: path.slice(4) };
  const trace = TRACE_ROUTE.exec(path);
  if (trace) return { name: 'trace', id: trace[1] };
  return { name: lookup(ROUTE_TITLES, path, null) && path !== 'doc' && path !== 'trace' ? path : 'workspace' };
}

function codePoints(text) {
  return [...String(text)].length;
}

// API offsets are Python code points; JavaScript strings index UTF-16 units.
// Returns null when the two coincide (no surrogates), else point -> unit offsets.
function codeUnitOffsets(text) {
  if (!/[\uD800-\uDFFF]/.test(text)) return null;
  const offsets = [0];
  let unit = 0;
  for (const ch of text) {
    unit += ch.length;
    offsets.push(unit);
  }
  return offsets;
}

function isExactSpan(text, span, length, unit) {
  return Boolean(span) && span.exact !== false && Number.isInteger(span.start) && Number.isInteger(span.end)
    && span.start >= 0 && span.start < span.end && span.end <= length && typeof span.text === 'string'
    && text.slice(unit(span.start), unit(span.end)) === span.text;
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

function paragraphRanges(text, start, end) {
  const source = text.slice(start, end);
  const ranges = [];
  const add = (from, to) => {
    while (from < to && source[from] === '\n') from += 1;
    while (to > from && source[to - 1] === '\n') to -= 1;
    if (source.slice(from, to).trim()) ranges.push([start + from, start + to]);
  };
  let cursor = 0;
  for (const match of source.matchAll(PARAGRAPH_BREAK)) {
    add(cursor, match.index);
    cursor = match.index + match[0].length;
  }
  add(cursor, source.length);
  return ranges;
}

function paragraphPieces(text, start, end, marks, own = null) {
  const pieces = [];
  let cursor = start;
  for (const mark of marks) {
    if (mark.end <= start || mark.start >= end) continue;
    const from = Math.max(mark.start, start);
    const to = Math.min(mark.end, end);
    if (from > cursor) pieces.push({ text: text.slice(cursor, from), keys: null });
    // keys: the whole highlight's (selection); held: the keys whose own span (``own``: key -> [start, end)) overlaps
    // this piece, which its title is made of (renderPieces; refutation round 10, page-1: a highlight split across
    // paragraphs gave each piece the whole highlight's title)
    const held = own ? mark.keys.filter(key => own.has(key) && own.get(key)[0] < to && own.get(key)[1] > from) : mark.keys;
    pieces.push({ text: text.slice(from, to), keys: mark.keys, held });
    cursor = to;
  }
  if (cursor < end) pieces.push({ text: text.slice(cursor, end), keys: null });
  return pieces;
}

// spans: [{key, start, end, text, exact}] in code points. A span is marked only when
// text[start:end] equals its text; anything else is reported as unlocated.
function layoutDocument(text, pages, spans) {
  const source = String(text || '');
  const offsets = codeUnitOffsets(source);
  const length = offsets ? offsets.length - 1 : source.length;
  const unit = point => (offsets ? offsets[point] : point);
  const located = [];
  const unlocated = [];
  for (const span of spans) {
    if (isExactSpan(source, span, length, unit)) located.push({ key: span.key, start: unit(span.start), end: unit(span.end) });
    else unlocated.push(span.key);
  }
  const marks = mergeSpans(located);
  const own = new Map(located.map(span => [span.key, [span.start, span.end]]));
  return {
    pages: pageRanges(pages, length, unit, source.length).map(page => ({
      page: page.page,
      paragraphs: paragraphRanges(source, page.start, page.end).map(([from, to]) => paragraphPieces(source, from, to, marks, own)),
    })),
    unlocated,
  };
}

// A member's value unlike the document's is that conflict (member_conflict, from context.is_member_conflict), never
// conflicting documentation; any conflict is shown as one, never as not documented (refutation r1, context-5). The
// question a closing charge block asks (date_asked, from context.charge_date_problem) is no conflict in the document.
function factValue(fact, labels, isDate = false) {
  if (!fact) return 'Not documented';
  if (fact.date_asked === true) return 'Date asked';
  if (fact.origin === 'conflict') return fact.member_conflict === true ? 'Member entry differs from the document' : 'Conflicting values documented';
  if (fact.origin === 'missing' || fact.value == null || fact.value === '' || fact.value === 'not_documented') return 'Not documented';
  const value = isDate ? (formatDate(fact.value, true) || String(fact.value)) : lookup(labels, fact.value, String(fact.value));
  return fact.origin === 'user' ? `${value} (entered)` : value;
}

function metaFact(fact, labels, name, isDate = false) {
  if (fact?.date_asked === true) return `${name} asked`;
  if (fact?.origin === 'conflict') return fact.member_conflict === true ? `${name}: member entry differs from the document` : `${name} conflict`;
  if (!fact || fact.origin === 'missing' || fact.value == null || fact.value === '') return `${name} not documented`;
  const value = isDate ? (formatDate(fact.value) || String(fact.value)) : lookup(labels, fact.value, String(fact.value));
  return fact.origin === 'user' ? `${value} (entered)` : value;
}

// Whitespace folded and cut to a length a chip can hold, with an ellipsis, as the checks quote a passage (checks.excerpt).
function excerpt(text, limit = EXCERPT_POINTS) {
  const flat = String(text ?? '').split(/\s+/).filter(Boolean).join(' ');
  const points = [...flat];
  return points.length <= limit ? flat : `${points.slice(0, limit - 1).join('').trimEnd()}…`;
}

// What a participant wrote, trimmed - unless it reads like a CPT descriptor (DESCRIPTOR_LIKE), which is never shown.
function participantText(value) {
  const text = typeof value === 'string' ? value.trim() : '';
  return DESCRIPTOR_LIKE.test(text) ? DESCRIPTOR_WITHHELD : text;
}

// 'A', 'A and B', 'A, B and C', as the engine joins names.
function joinWords(items) {
  return items.length <= 2 ? items.join(' and ') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;
}

// Participant names in harness order (Corti, Astra, Fable), any other after them as served.
function inHarnessOrder(names) {
  const rank = name => (Object.hasOwn(PARTICIPANT_LABELS, name) ? Object.keys(PARTICIPANT_LABELS).indexOf(name) : 99);
  return [...names].sort((a, b) => rank(a) - rank(b));
}

// Whether the payload is harness@2's with a model participant in play (HARNESS.md 12.6): harness.phase is 1 or 2, or a
// participant row carries a peer review. A payload served before harness@2, and a Corti-only one (phase 0, I1), draw
// none of its rows and the page reads as before.
function harness2(doc) {
  const harness = doc?.harness;
  if (!harness || typeof harness !== 'object') return false;
  if (harness.phase === 1 || harness.phase === 2) return true;
  return objects(harness.participants).some(row => row.peer && typeof row.peer === 'object' && !Array.isArray(row.peer) && Object.keys(row.peer).length > 0);
}

// The phase each participant first proposed a code in (proposal.phases, HARNESS.md 11.1); {} when none is served.
function proposalPhases(proposal) {
  const phases = proposal?.phases;
  return phases && typeof phases === 'object' && !Array.isArray(phases) ? phases : {};
}

// A code no participant proposed in its independent reading and Corti did not propose: first proposed after peer
// review, never shown as independent (HARNESS.md 11.1).
function peerPhaseOnly(proposal) {
  const proposers = strings(proposal?.proposed_by);
  const phases = proposalPhases(proposal);
  return proposers.length > 0 && !proposers.includes('corti') && proposers.every(name => phases[name] === 'peer_review');
}

// The assess and peer-review jobs of the current revision by phase (HARNESS.md 12.1): an assess a peer stage follows
// before any other assess is a first assessment; one after a peer stage is the second (final) assessment or a
// re-assessment of it. A peer row and the second assessment's row show only jobs after the latest first assessment, so
// an earlier chain's outcome is never shown as the current one's. An assess queued just after the final one (a context
// change's, or a confirmation's re-assessment) reads as the second until a peer stage follows it: the stages say no
// more.
function phasedJobs(stages) {
  let firstAt = -1;
  let secondAt = -1;
  let peered = false;
  stages.forEach((stage, index) => {
    const kind = stage?.kind;
    if (PEER_KINDS.has(kind)) {
      peered = true;
    } else if (CHAIN_KINDS.has(kind)) {
      peered = false;
    } else if (kind === 'assess') {
      const next = stages.slice(index + 1).find(item => PEER_KINDS.has(item?.kind) || CHAIN_KINDS.has(item?.kind) || item?.kind === 'assess');
      if (PEER_KINDS.has(next?.kind) || !peered) firstAt = index;
      else secondAt = index;
    }
  });
  const after = kind => stages.slice(firstAt + 1).filter(stage => stage?.kind === kind).pop() || null;
  return { assess: firstAt >= 0 ? stages[firstAt] : null, assess2: secondAt > firstAt ? stages[secondAt] : null, astra_peer: after('astra_peer'), fable_peer: after('fable_peer') };
}

// "Confirmed from Fable's located passage by <reviewer>" (HARNESS.md 11.3), as the engine words a confirmation.
function confirmedFrom(confirmation) {
  const owners = inHarnessOrder(strings(confirmation?.located_by)).map(name => `${lookup(PARTICIPANT_LABELS, name, name)}'s`);
  const reviewer = textValue(confirmation?.confirmed_by) || 'a reviewer whose name was not recorded';
  return `Confirmed from ${owners.length ? joinWords(owners) : 'a participant\'s'} located passage by ${reviewer}`;
}

// Who located a candidate's passage, and in which phase each did (candidate.phases; its phase where none is served):
// "Located by Astra and Fable in their independent first readings", "..., and by Fable in peer review".
function locatedBy(candidate) {
  const phases = candidate?.phases && typeof candidate.phases === 'object' && !Array.isArray(candidate.phases) ? candidate.phases : {};
  const groups = new Map();
  for (const name of inHarnessOrder(strings(candidate?.located_by))) {
    const phase = Object.hasOwn(phases, name) ? phases[name] : candidate.phase;
    const key = Object.hasOwn(LOCATED_PHASES, phase) ? phase : '';
    groups.set(key, [...(groups.get(key) || []), lookup(PARTICIPANT_LABELS, name, name)]);
  }
  const said = [...groups].map(([phase, names]) => {
    const where = !phase ? 'in a phase that was not recorded' : names.length === 1 ? LOCATED_PHASES[phase] : LOCATED_PHASES[phase].replace(' its ', ' their ').replace(/reading$/, 'readings');
    return `${joinWords(names)} ${where}`;
  });
  return said.length ? `Located by ${said.join(', and by ')}.` : 'Who located this passage was not recorded.';
}

// Whether a participant's reference concerns ``code``: a fact ref names its code (fact:<source>:<code>:<field>); a
// policy passage names none, so it concerns every code. Only a ref CPT Studio's own tool results returned is read so
// (``own``): one a participant cites that its run's tool calls never returned is its own text, read for no code, so it
// is listed with every code, as a policy passage is (refutation round 4, shapes-3: a cited "fact:" ref was placed by
// its own text).
function refConcerns(ref, code, own = true) {
  const text = textValue(ref);
  if (!own || !text.startsWith('fact:')) return Boolean(text);
  const parts = text.split(':');
  return parts.length >= 4 && parts[parts.length - 2] === code;
}

// A value a participant wrote into a reference, a tool call's tool or its arguments is shown only in the shape it may
// take (HARNESS.md 12.4 as amended after refutation round 4, the session's D9; participants.peer): the API serves each
// so already, and the page shows nothing else - a value served in no such shape is named by its length here too
// ('colonoscopy-flexible-with-biopsy-single-or-multiple', a descriptor written with hyphens, passed DESCRIPTOR_LIKE).
const SHORT_ID = /^[A-Za-z0-9]{1,8}$/;
const REF_KEY = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$/;  // CPT Studio's own reference key (reports.REF_SHAPE)
const WITHHELD_WORDS = /^a value of [0-9][0-9,]* characters? \(not shown\)$/;  // participants.peer.withheld's words

// A value a participant wrote, named only by its length, in CPT Studio's words (participants.peer.withheld).
function byLength(text) {
  const size = [...text].length;
  return `a value of ${size.toLocaleString('en-US')} character${size === 1 ? '' : 's'} (not shown)`;
}

// ``value`` as given when it is text in ``shape`` (or CPT Studio's own "a value of N characters (not shown)"), any
// other text by its length, and a value that is not text by the length of its JSON; '' stays ''.
function inShape(value, shape) {
  if (typeof value !== 'string') return byLength(JSON.stringify(value === undefined ? null : value));
  return !value || shape.test(value) || WITHHELD_WORDS.test(value) ? value : byLength(value);
}

// A reference a participant says it used (references.used[], references_used[]): as given only when its own run's tool
// calls returned it (``retrieved``: CPT Studio's own key), otherwise only as a short id of letters and digits, or by
// its length.
function shownReference(item) {
  const ref = item && typeof item.ref === 'string' ? item.ref : '';
  return item?.retrieved === true && REF_KEY.test(ref) ? ref : inShape(ref, SHORT_ID);
}

// A tool call's tool and arguments as the trace shows them (refutation round 4, shapes-4; participants.peer.shown_tool,
// shown_arguments): a tool CPT Studio has, and an object of the tools' own fields, each value in its own shape - every
// code a CPT or HCPCS code's, a date YYYY-MM-DD or '', a topic one of the policy topics; anything else by its length.
const TOOL_NAMES = /^(?:cms_code_facts|cms_policy_passages)$/;
const TOOL_FIELDS = {
  codes: /^(?:[0-9]{4}[0-9A-Z]|[A-Z][0-9]{4})$/,  // each code of the list (peer.code_shaped)
  date_of_service: /^(?:[0-9]{4}-[0-9]{2}-[0-9]{2})?$/,
  topic: /^(?:pfs_indicator_definitions|ncci_endoscopy_rules|multiple_endoscopy_payment)$/,
};
const NO_SHAPE = /(?!)/;

function shownArguments(args) {
  if (args === null || args === undefined) return null;
  if (typeof args === 'object' && !Array.isArray(args) && Object.keys(args).every(key => Object.hasOwn(TOOL_FIELDS, key))) {
    return Object.fromEntries(Object.entries(args).map(([key, value]) => [key, key !== 'codes' ? inShape(value, TOOL_FIELDS[key])
      : Array.isArray(value) ? value.map(item => inShape(item, TOOL_FIELDS.codes)) : inShape(value, NO_SHAPE)]));
  }
  return inShape(args, NO_SHAPE);
}

// The documented text the reader kept as the evidence of a service date it could not use (an unread date form, another
// occurrence's date, a dated title or "Date:" line): documented text, quoted, never called "not documented" - as the
// service date check and its question quote it (checks._date_problem; refutation gi2, occurrence RC5: the chip said "Not
// documented" beside the check quoting it). '' wherever factValue states something else: a value, a conflict.
function keptDateEvidence(fact) {
  if (!fact || fact.origin === 'conflict') return '';
  if (!(fact.origin === 'missing' || fact.value == null || fact.value === '' || fact.value === 'not_documented')) return '';
  const span = (Array.isArray(fact.evidence) ? fact.evidence : []).find(item => typeof item?.text === 'string' && item.text.trim());
  return span ? excerpt(span.text) : '';
}

// Whether the assessment shown asks the date: its encounter question on the service date is open.
function serviceDateAsked(doc) {
  return openClarifications(doc).some(item => item.scope === 'encounter' && item.fact === 'service_date');
}

// The SERVICE DATE chip of the source paper, and the service date of the review header.
function serviceDateChip(doc) {
  const fact = doc?.context?.facts?.service_date;
  const kept = keptDateEvidence(fact);
  if (!kept) return factValue(fact, null, true);
  return `${serviceDateAsked(doc) ? 'Asked — ' : ''}“${kept}” is not read as the date of service`;
}

function serviceDateMeta(doc) {
  const fact = doc?.context?.facts?.service_date;
  const kept = keptDateEvidence(fact);
  if (!kept) return metaFact(fact, null, 'Service date', true);
  return `${serviceDateAsked(doc) ? 'Service date asked — ' : 'Service date: '}“${kept}” is not read as the date of service`;
}

function proposalsIn(assessment, bucket) {
  return (assessment?.proposals || []).filter(proposal => proposal.bucket === bucket);
}

function openClarifications(doc) {
  return (doc.clarifications || []).filter(item => item.state === 'open');
}

// Encounter-scoped questions concern every service, so they stay a card of their own.
function clarificationsFor(proposal, doc) {
  const ids = proposal.clarification_ids || [];
  return openClarifications(doc).filter(item => item.scope !== 'encounter' && (item.proposal_id === proposal.id || ids.includes(item.id)));
}

function familyLabel(doc, family) {
  const known = [...(doc.routing?.families || []), ...(doc.assessment?.proposals || [])].find(item => item.family === family);
  return known?.family_label || known?.label || family;
}

// The same rule as the reviewed report: an agent's decision or an agent's reinstatement, in any bucket.
function hasAgentDecision(doc) {
  return (doc.assessment?.proposals || []).some(p => (p.decision && p.decision_state !== 'undecided' && p.decision.reviewer_kind === 'agent')
    || p.reinstated_by?.reviewer_kind === 'agent');
}

// Context and addenda are refused by the API while a stage runs (409), so they are offered only when idle.
function canEdit(doc) {
  return Boolean(doc.permissions?.can_review) && !doc.pipeline?.busy;
}

function exportStatusText(doc) {
  const readiness = doc.readiness || {};
  const blockers = (readiness.blockers || []).filter(Boolean);
  if (readiness.reviewed === true) {
    return `Reviewed — every selected code has a current decision.${hasAgentDecision(doc) ? ' Includes agent-executed synthetic review — not clinical approval.' : ''}`;
  }
  const head = readiness.draft === true ? 'Draft — not reviewed.' : 'No report can be generated yet.';
  return blockers.length ? `${head} Still needed: ${blockers.join('; ')}.` : head;
}

// --- rendering (pure string builders) ----------------------------------------------

const state = {
  session: null, route: null, routeToken: 0, doc: null, docKey: '', layout: null,
  currentTab: 'codes', selectedEvidence: [], poll: { timer: 0, count: 0, errors: 0 },
  upload: { file: null, paste: false, busy: false }, review: null, addendum: null,
  pending: new Set(), toastTimer: 0, leaving: false,
};

function categoryName() {
  return state.session?.workspace?.category?.name || 'Gastroenterology';
}

function badge(tone, label, iconName = '') {
  return `<span class="status ${tone}">${iconName ? icon(iconName) : ''}${escapeHtml(label)}</span>`;
}

function stateBadge(stateName, label) {
  const iconName = stateName === 'reviewed' ? 'check' : stateName === 'processing' ? 'clock' : '';
  return badge(lookup(STATE_TONES, stateName, 'gray'), label || String(stateName || 'Unknown').replace(/_/g, ' '), iconName);
}

function proposalBadge(proposal) {
  if (proposal.decision_state === 'approved') return badge('green', proposal.decision?.reviewer_kind === 'agent' ? 'Approved · agent' : 'Approved', 'check');
  if (proposal.decision_state === 'rejected') return badge('gray', 'Rejected');
  if (proposal.decision_state === 'reinstated') return badge('green', 'Reinstated for review');
  if (proposal.decision_state === 'exclusion_confirmed') return badge('gray', 'Exclusion confirmed');
  if (proposal.status === 'excluded') return badge('gray', 'Excluded');
  if (proposal.status === 'needs_clarification') return badge('amber', 'Needs clarification');
  if (proposal.status === 'ready') return badge('green', proposal.status_label || 'Ready for review');
  return badge('gray', proposal.status_label || 'Not reviewable');
}

const LIST_HEADER = '<div class="list-header"><span>DOCUMENT</span><span>REVIEW STATUS</span><span class="date-header">SERVICE DATE</span><span></span></div>';

// A reviewed encounter whose coding is incomplete (coding_state: the encounter view's coding completeness) - "Reviewed"
// alone reads as done (refutation gi2, demo R10: ho-09 was "Reviewed" with its flexible sigmoidoscopy unresolved).
function reviewedIncomplete(encounter) {
  return encounter?.state === 'reviewed' && encounter.coding_state === 'incomplete';
}

function rowStateLabel(encounter) {
  return reviewedIncomplete(encounter) ? `${encounter.state_label || 'Reviewed'} · coding incomplete` : encounter.state_label;
}

// The review queue lists what the API says waits on a member (queue_reasons: an open question, a code to decide, a request
// to reconcile, coding left incomplete, a second review that can be asked for) - every such row, whatever its state
// (refutation gi2, demo RC6: ho-06 and ho-09 were off a queue of three states). A row served without the field keeps
// those three states.
function inQueue(encounter) {
  return Array.isArray(encounter?.queue_reasons) ? encounter.queue_reasons.length > 0 : QUEUE_STATES.has(encounter?.state);
}

// The served reasons a queued row's meta line names; what its open-question count or its badge already says is not repeated.
function queueReasonLabels(encounter) {
  const reasons = Array.isArray(encounter.queue_reasons) ? encounter.queue_reasons : [];
  const said = reasons.filter(reason => !(reason === 'incomplete' && reviewedIncomplete(encounter))).map(reason => lookup(QUEUE_REASON_LABELS, reason, ''));
  return [...new Set(said.filter(Boolean))];
}

// A list row's service date the reader kept as evidence but could not use (encounter_summary's service_date_evidence):
// quoted, never "not documented", as the review page's chip quotes it (gi2 integration, occurrence RC5). '' when none.
function listedDateEvidence(encounter, prefix) {
  const text = typeof encounter?.service_date_evidence === 'string' ? encounter.service_date_evidence.trim() : '';
  return text ? `${prefix}“${excerpt(text, 32)}”` : '';
}

function documentRow(encounter, queued = false) {
  const tone = reviewedIncomplete(encounter) ? 'amber' : lookup(STATE_TONES, encounter.state, 'gray');
  const families = Array.isArray(encounter.families) && encounter.families.length ? encounter.families.join(' · ') : categoryName();
  const kind = lookup(SOURCE_KINDS, encounter.source_kind, encounter.source_kind ? String(encounter.source_kind).toUpperCase() : '');
  const open = Number.isInteger(encounter.open_clarifications) && encounter.open_clarifications > 0 ? plural(encounter.open_clarifications, 'open question', 'open questions') : '';
  const meta = [kind, families, open, ...(queued ? queueReasonLabels(encounter) : [])].filter(Boolean).join(' · ');
  const status = reviewedIncomplete(encounter) ? badge('amber', rowStateLabel(encounter)) : stateBadge(encounter.state, encounter.state_label);
  return `<a class="document-row" href="#doc/${escapeHtml(encodeURIComponent(encounter.id))}"><span class="doc-row-main"><span class="doc-file-icon${tone === 'amber' ? ' amber' : ''}">${icon('file')}</span><span><strong>${escapeHtml(encounter.title || 'Untitled document')}</strong><small>${escapeHtml(meta)}</small></span></span><span>${status}</span><span class="doc-row-date">${escapeHtml(formatDate(encounter.service_date) || (encounter.service_date_asked === true ? 'Date asked' : encounter.service_date_conflict === true ? 'In conflict' : listedDateEvidence(encounter, 'Not read: ') || 'Not documented'))}</span>${icon('chevron', 'row-arrow')}</a>`;
}

function listRows(name, encounters) {
  if (name === 'queue') return encounters.filter(inQueue);
  return name === 'workspace' ? encounters.slice(0, 5) : encounters;
}

function listBody(name, encounters) {
  const rows = listRows(name, encounters);
  const empty = { workspace: 'No documents yet. Start with a synthetic GI document.', documents: 'No documents yet. Use New document to upload a synthetic GI document or paste its text.', queue: 'Nothing is waiting for review.' }[name];
  return LIST_HEADER + (rows.length ? rows.map(row => documentRow(row, name === 'queue')).join('') : `<p class="empty-state">${escapeHtml(empty)}</p>`);
}

function listDescription(name, encounters) {
  if (name === 'queue') {
    const count = listRows('queue', encounters).length;
    return count ? `${count === 1 ? 'One document waits' : `${count} documents wait`} on a workspace member: a clarification, a review decision, a reconciliation, a second review that can be asked for, or coding left incomplete.` : 'No document waits on a workspace member for a clarification, a review decision, a reconciliation, a second review or incomplete coding.';
  }
  return `${plural(encounters.length, 'synthetic document', 'synthetic documents')} in this workspace.`;
}

function inviteMarkup(encounters) {
  const recent = encounters?.[0];
  if (encounters === null) return `<span class="sample-icon">${icon('file')}</span><span class="sample-text"><strong>Loading recent documents…</strong><p>One moment.</p></span>`;
  if (!recent) return `<span class="sample-icon">${icon('file')}</span><span class="sample-text"><strong>No documents yet</strong><p>Upload a synthetic GI document to see proposals beside the source.</p></span><button type="button" class="button secondary" data-action="upload">New document ${icon('plus')}</button>`;
  const detail = ['Most recent', rowStateLabel(recent), formatDate(recent.service_date) || (recent.service_date_asked === true ? 'service date asked' : recent.service_date_conflict === true ? 'service date in conflict' : listedDateEvidence(recent, 'service date not read: ') || 'service date not documented')].filter(Boolean).join(' · ');
  return `<span class="sample-icon">${icon('file')}</span><span class="sample-text"><strong>${escapeHtml(recent.title || 'Untitled document')}</strong><p>${escapeHtml(detail)}</p></span><button type="button" class="button secondary" data-open="${escapeHtml(recent.id)}">Open review ${icon('arrow')}</button>`;
}

function overviewView() {
  const held = state.session?.interpreter?.held === true ? interpreterHoldCard(state.session.interpreter) : '';
  return `<section class="view-entrance">${held}<div class="heading-row home-heading"><div><span class="eyebrow">A CLEARER VIEW OF EVERY CODE</span><h1>Precision starts<br>with the <em>evidence.</em></h1><p>A focused workspace to turn clinical documentation into evidence-backed CPT suggestions.</p></div><div class="heading-actions"><span class="only-tag">CPT ONLY</span><button type="button" class="button primary" data-action="upload" aria-label="New document">${icon('plus')}<span class="desktop-label">New document</span></button></div></div>
  <div class="home-grid"><section class="upload-panel"><div class="panel-heading">${icon('file')}<h2>Start a coding review</h2><span class="small-badge">One encounter at a time</span></div><button type="button" class="drop-zone" id="overviewDrop" data-action="upload"><span class="upload-icon">${icon('upload')}</span><strong>Bring the original document.</strong><span>Choose a file, drop it here or paste the text</span><span>PDF, DOCX or TXT</span></button><div class="upload-footnote">${icon('info')}<span>Synthetic documents only. Do not upload real patient information.</span></div><div class="sample-invite" id="recentInvite">${inviteMarkup(null)}</div></section>
  <aside class="story-panel"><span class="eyebrow">BUILT AROUND THE CLINICAL STORY</span><h2>A clearer path.<br>From note to code.</h2><ol class="workflow-list"><li><span class="workflow-number">01</span><span><strong>Read the whole note</strong><p>Begin with the original documentation and encounter context.</p></span></li><li><span class="workflow-number">02</span><span><strong>Connect every suggestion</strong><p>See the source passages that support the proposed code.</p></span></li><li><span class="workflow-number">03</span><span><strong>Make a clear decision</strong><p>Review the evidence and resolve gaps before approval.</p></span></li></ol><div class="story-bottom">${icon('link')}Evidence beside the decision. Always.</div></aside></div>
  <div class="section-heading"><h2>Recent documents</h2><a href="#documents">View all ${icon('arrow')}</a></div><div class="document-list" id="documentsTable">${LIST_HEADER}<p class="empty-state">Loading documents…</p></div></section>`;
}

function documentsView(name) {
  const queue = name === 'queue';
  return `<section class="view-entrance"><div class="heading-row documents-heading"><div><span class="eyebrow">${queue ? 'A PLACE FOR THE OPEN QUESTIONS' : 'THE ORIGINAL, ALWAYS IN VIEW'}</span><h1>${queue ? 'Review queue.' : 'Your documents.'}</h1><p>${queue ? 'Keep missing information visible, so uncertainty becomes a clear next step.' : 'Keep source notes, supporting evidence and coding decisions together.'}</p></div><div class="heading-actions"><button type="button" class="button primary" data-action="upload">${icon('plus')}New document</button></div></div><p class="section-description" id="listDescription">Loading…</p>${queue ? '' : `<label class="search-field">${icon('search')}<input id="documentSearch" aria-label="Search documents" placeholder="Search documents…" autocomplete="off"></label><div style="height:18px"></div>`}<div class="document-list" id="documentsTable">${LIST_HEADER}<p class="empty-state">Loading documents…</p></div><p class="checks-disclaimer">${queue ? 'Documents waiting on a workspace member: a clarification, a review decision, a provider reconciliation, a second review that can be asked for, or coding left incomplete. A document being processed waits on its stages instead.' : 'Synthetic documents only. Each review decision is tied to the revision it was made on.'}</p></section>`;
}

function howItWorksView() {
  const mode = lookup({ live: 'Provider mode in this deployment: live requests to the configured provider.', replay: 'Provider mode in this deployment: REPLAY — recorded responses, not live output.', disabled: 'Provider mode in this deployment: disabled — no proposals are requested.' }, state.session?.provider_mode, '');
  return `<section class="view-entrance"><div class="heading-row how-heading"><div><span class="eyebrow">A FOCUSED PRODUCT, BY DESIGN</span><h1>A reason behind<br><em>every suggestion.</em></h1><p>A standalone CPT workspace that keeps the original clinical story and the coding review connected.</p></div><button type="button" class="button primary" data-action="upload">Start a coding review ${icon('arrow')}</button></div><div class="flow-overview"><article class="flow-card"><span class="step">01</span><h2>The source<br>comes first.</h2><p>Upload the original PDF or Word document, or paste the note. The text is extracted as written; scanned pages are read with OCR where it is available, and anything that could not be read is listed.</p></article><article class="flow-card"><span class="step">02</span><h2>Suggestions<br>need support.</h2><p>A coding provider proposes CPT codes. A code is kept only with exact source passages, then checked separately against the connected reference files for the service date. Whatever cannot be checked is labelled not verified.</p></article><article class="flow-card"><span class="step">03</span><h2>Review makes<br>the difference.</h2><p>Answer focused clarifications, approve or reject each code, confirm or reinstate each code a documentation check excluded, and download a draft or reviewed report. A changed source invalidates earlier decisions.</p></article></div><div class="how-note"><strong>This is a synthetic demonstration.</strong><br>Licensed CPT descriptors and NCCI procedure-to-procedure edits are not connected in this release, so descriptors are withheld and code-set validity and PTP edits stay not verified. The documentation checks read declared wording, layouts and check boxes, and they can miss wording they do not recognise, so every code needs a reviewer who reads the whole document. Accuracy has not been independently evaluated; no accuracy percentage or payment guarantee is claimed.${mode ? `<br>${escapeHtml(mode)}` : ''}</div><button type="button" class="button secondary" data-action="about">${icon('info')}About CPT Studio</button></section>`;
}

function messageView(title, detail, retry = false) {
  return `<section class="view-entrance"><a class="back-link" href="#documents">${icon('arrow')}All documents</a><div class="check-list-card"><p class="empty-state"><strong>${escapeHtml(title)}</strong><br>${escapeHtml(detail)}</p>${retry ? '<p class="empty-state"><button type="button" class="button secondary" data-action="retry">Try again</button></p>' : ''}</div></section>`;
}

// A support that was not checked (status not_applicable: the documented service or act is not established as performed)
// says nothing either way about its passages (refutation 7c8, reports-4).
function supportChecked(proposal) {
  return proposal?.support?.status !== 'not_applicable';
}

// The source passages CPT Studio selected are the coded act's own only where the engine matched the code to the act
// (support.acts) or where the act is the service itself (reason 'service': a base or E/M code); a support served with
// no acts list (the elsewhere path) is checked against the act's own passages too. Otherwise - no act read
// ('own_passage': the status was read from the cited passage itself; 'profile_unknown') - they are the documented
// service's own passages, which the provider's were checked against, so neither is said to show, or not to show, the
// coded act (refutation round 6, R6-MEANING, ownership-5: a combined report's "Procedures: EGD and colonoscopy" was
// listed under "Source passages that show the coded act" beside the cited "Biopsies were taken with cold forceps.",
// said not to show it, the very passage the code's status was read from). One rule for the chips (evidenceChips) and
// the source panel's highlights (documentLayout), which titled those passages "Evidence for <code>" (found at the
// integration of R6-MEANING).
function serviceOnlySupport(proposal) {
  const acts = proposal?.support?.acts;
  return supportChecked(proposal) && Array.isArray(acts) && !acts.length && proposal?.support?.reason !== 'service';
}

// The provider's passages (their indexes) that a checked support says do not show the coded act (support.unrelated),
// where its source passages are the act's own (not serviceOnlySupport): the chip says "cited by the provider; does not
// show the coded act" (evidenceChips), and the source panel titles them so too, never "Evidence for <code>" (refutation
// round 7, display-6: a Ready 45385 whose cited "A 9 mm pedunculated polyp in the sigmoid colon was seen." was titled
// "Evidence for 45385" beside that chip). Where one highlight also carries a passage of the same code that shows the act
// - a longer passage of the provider's that holds it, a source passage CPT Studio selected at the same place, or a
// separate passage that another code's passage joins into one highlight - the title says the highlight holds passages
// of both kinds for that code, never "Evidence for <code>" and that passage's own title side by side as if of one
// passage (refutation round 8, page-1; round 9, page-3: "Overlapping passages" was said of two separate sentences;
// renderPieces). A service-only support's unrelated passages are only "cited by the provider".
function passagesNotShowingTheAct(proposal) {
  const unrelated = proposal?.support?.unrelated;
  return new Set(supportChecked(proposal) && !serviceOnlySupport(proposal) && Array.isArray(unrelated) ? unrelated : []);
}

function documentLayout(doc) {
  const spans = [];
  const codes = new Map();
  const unchecked = new Set();
  const services = new Set();
  const cited = new Set();
  for (const proposal of proposalsIn(doc.assessment, 'selected')) {
    const notTheAct = passagesNotShowingTheAct(proposal);
    (proposal.evidence || []).forEach((evidence, index) => {
      const key = `${proposal.id}:${index}`;
      spans.push({ ...evidence, key });
      codes.set(key, proposal.code);
      if (notTheAct.has(index)) cited.add(key);
    });
    // Source passages CPT Studio selected because the provider's passages do not show the coded act - or, for a support
    // that was not checked, the documented service's passages, which are never marked as evidence for the code; nor are
    // the documented service's passages of a support that read no act (serviceOnlySupport).
    (proposal.support?.source || []).forEach((evidence, index) => {
      const key = `${proposal.id}:s${index}`;
      spans.push({ ...evidence, key });
      codes.set(key, proposal.code);
      if (!supportChecked(proposal)) unchecked.add(key);
      else if (serviceOnlySupport(proposal)) services.add(key);
    });
  }
  const layout = layoutDocument(doc.revision?.text || '', doc.revision?.pages, spans);
  return { pages: layout.pages, unlocated: new Set(layout.unlocated), codes, unchecked, services, cited };
}

function renderPieces(pieces, layout) {
  return pieces.map(piece => {
    if (!piece.keys) return escapeHtml(piece.text);
    const unchecked = layout.unchecked || new Set();
    const services = layout.services || new Set();
    const cited = layout.cited || new Set();
    const codesIn = keys => [...new Set(keys.map(key => layout.codes.get(key)))];
    const codesOf = keys => codesIn(keys).join(', ');
    // the title says what this piece holds (paragraphPieces' held keys), never what another piece of its highlight does
    const held = piece.held || piece.keys;
    const evidence = held.filter(key => !unchecked.has(key) && !services.has(key) && !cited.has(key));
    const notTheAct = held.filter(key => cited.has(key));
    const service = held.filter(key => services.has(key));
    const notChecked = held.filter(key => unchecked.has(key));
    // A code with both kinds of passage in this highlight is titled once, as holding both (page-1, page-3).
    const both = codesIn(evidence).filter(code => codesIn(notTheAct).includes(code));
    const evidenceOnly = codesIn(evidence).filter(code => !both.includes(code));
    const notTheActOnly = codesIn(notTheAct).filter(code => !both.includes(code));
    const title = [evidenceOnly.length ? `Evidence for ${evidenceOnly.join(', ')}` : '', notTheActOnly.length ? `Passage the provider cited for ${notTheActOnly.join(', ')}, which does not show the coded act` : '', ...both.map(code => `Passages for ${code} in this highlight: evidence for ${code}, and a passage the provider cited for ${code} that does not show the coded act`), service.length ? `Passage of the documented service for ${codesOf(service)}` : '', notChecked.length ? `Passage of the documented service for ${codesOf(notChecked)}, not checked against the coded act` : ''].filter(Boolean).join('; ');
    return `<button type="button" class="evidence-mark" data-evidence="${escapeHtml(piece.keys[0])}" data-keys="${escapeHtml(piece.keys.join(' '))}" title="${escapeHtml(title)}">${escapeHtml(piece.text)}</button>`;
  }).join('');
}

function sourceName(revision) {
  return revision.source_file?.name || lookup({ paste: 'Pasted clinical text', addendum: 'Document with addendum' }, revision.kind, 'Original document');
}

function sourcePanel(doc, layout) {
  const revision = doc.revision || {};
  const extraction = revision.extraction || {};
  const facts = doc.context?.facts || {};
  const hasText = Boolean(revision.text);
  const total = Math.max(Number.isInteger(extraction.page_count) ? extraction.page_count : 0, layout.pages.length);
  const ocr = Array.isArray(extraction.ocr_pages) && extraction.ocr_pages.length ? `OCR on ${extraction.ocr_pages.length === 1 ? 'page' : 'pages'} ${extraction.ocr_pages.join(', ')}` : '';
  const subtitle = [categoryName(), lookup(METHOD_LABELS, extraction.method, ''), revision.number ? `Revision ${revision.number}` : '', ocr].filter(Boolean).join(' · ');
  const notes = [];
  if (revision.kind === 'addendum') notes.push(`Revision ${revision.number} appends an addendum to the earlier text; decisions made on earlier revisions no longer apply.`);
  if (extraction.status === 'pending') notes.push('The text is still being extracted.');
  for (const message of extraction.messages || []) notes.push(message);
  const metadata = [['SERVICE DATE', serviceDateChip(doc)], ['SETTING', factValue(facts.setting, SETTING_LABELS)], ['PATIENT STATUS', factValue(facts.patient_status, PATIENT_LABELS)], ['BILLING CONTEXT', factValue(facts.billing_context, BILLING_LABELS)]]
    .map(([label, value]) => `<span><b>${label}</b>${escapeHtml(value)}</span>`).join('');
  const header = `<span class="paper-eyebrow">${escapeHtml(`${state.session?.workspace?.name || 'CPT Studio'} · synthetic document`.toUpperCase())}</span><h3>${escapeHtml(sourceName(revision))}</h3><p class="paper-subtitle">${escapeHtml(subtitle)}</p><div class="paper-metadata">${metadata}</div>`;
  const emptyText = extraction.status === 'failed' ? 'No text could be extracted from this document.' : 'The document text will appear here once extraction finishes.';
  const papers = layout.pages.map((page, index) => {
    const body = page.paragraphs.map(pieces => `<p class="source-text">${renderPieces(pieces, layout)}</p>`).join('');
    return `<article class="source-paper" data-page="${escapeHtml(page.page)}" aria-label="${escapeHtml(`Page ${page.page}`)}">${index === 0 ? header : ''}${body || (index === 0 && !hasText ? `<p class="card-empty">${emptyText}</p>` : '')}<div class="paper-footer"><span>SYNTHETIC DOCUMENT · NOT FOR BILLING</span><span>${hasText ? escapeHtml(`${pad(page.page)} / ${pad(total)}`) : ''}</span></div></article>`;
  }).join('');
  const pageLabel = hasText ? `Page ${layout.pages[0].page} of ${total}` : 'No text extracted';
  const original = revision.source_file ? `<a href="/ops/api/encounters/${escapeHtml(encodeURIComponent(doc.id))}/original" download>${icon('download')}Download original</a>` : '';
  return `<section class="source-panel" aria-label="Source document"><div class="source-toolbar">${icon('file')}<h2>Original document</h2><span class="page-number" id="pageNumber" data-total="${escapeHtml(total)}">${escapeHtml(pageLabel)}</span></div><div class="source-paper-wrap" id="sourceScroll">${notes.map(note => `<div class="reference-note">${icon('info')}<span>${escapeHtml(note)}</span></div>`).join('')}${papers}</div><div class="source-bottom"><span></span>Original text as extracted${original}</div></section>`;
}

function reviewMeta(doc) {
  const facts = doc.context?.facts || {};
  const items = [serviceDateMeta(doc), metaFact(facts.setting, SETTING_LABELS, 'Setting'), categoryName(), doc.revision?.number ? `Revision ${doc.revision.number}` : ''];
  const extracted = ['ok', 'partial'].includes(doc.revision?.extraction?.status);
  const edit = canEdit(doc) && extracted ? '<span><button type="button" class="meta-link" data-action="edit-context">Edit context</button></span>' : '';
  return items.filter(Boolean).map(item => `<span>${escapeHtml(item)}</span>`).join('') + edit;
}

function checkItem(tone, iconName, title, detail, extra = '') {
  return `<div class="check-item${tone ? ` ${tone}` : ''}">${icon(iconName)}<div><strong>${escapeHtml(title)}</strong>${detail ? `<p>${escapeHtml(detail)}</p>` : ''}${extra}</div></div>`;
}

function groupLabel(text) {
  return `<div class="evidence-label">${escapeHtml(text)}</div>`;
}

function sectionHeading(title, count) {
  return `<div class="section-heading"><h2>${escapeHtml(title)}</h2><span class="small-badge">${escapeHtml(count)}</span></div>`;
}

function decisionButton(action, proposal) {
  const [, kind, label, iconName] = ACTION_BUTTONS.find(([name]) => name === action);
  return `<button type="button" class="button ${kind}" data-decision="${action}" data-proposal="${escapeHtml(proposal.id)}">${label}${iconName ? ` ${icon(iconName)}` : ''}</button>`;
}

function cardActions(proposal) {
  const allowed = Array.isArray(proposal.allowed_actions) ? proposal.allowed_actions : [];
  const buttons = ACTION_BUTTONS.filter(([name]) => allowed.includes(name)).map(([name]) => decisionButton(name, proposal));
  return buttons.length ? `<div class="code-card-actions">${buttons.join('')}</div>` : '';
}

function decisionLine(proposal) {
  const decision = proposal.decision;
  if (!decision || proposal.decision_state === 'undecided') return '';
  const title = `${lookup(DECISION_TITLES, decision.action, 'Decision recorded')} by ${decision.reviewer || 'a reviewer whose name was not recorded'}`;
  // decided_at is when the reviewer decided; a carried decision also shows when it was carried.
  const carried = decision.carried_from && decision.carried_at ? `carried to this assessment ${formatTimestamp(decision.carried_at)}` : '';
  const detail = [formatTimestamp(decision.decided_at || decision.created_at), carried, decision.revision_number ? `revision ${decision.revision_number}` : '', decision.reviewer_kind === 'agent' ? 'agent-executed synthetic review — not clinical approval' : 'synthetic review — not clinical approval'].filter(Boolean).join(' · ');
  return `<div class="review-insight">${icon('shield')}<div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(detail)}</p>${decision.note ? `<p>${escapeHtml(`Note: ${decision.note}`)}</p>` : ''}</div></div>`;
}

// A code card states the NCCI procedure-to-procedure limit once (HARNESS.md I4: PTP is always "not verified"): in its
// status line wherever that is shown (codeStatusLines: the API's reference_check detail says it, or the page's own
// parenthetical does); else in its "Not verified" note, from its ncci.ptp check; else in its modifier considerations.
// Each later place leaves it out (refutation round 3, truth-6: every real card stated it in all three).
function ptpInStatusLine(proposal) {
  return Array.isArray(proposal.proposed_by) || Boolean(proposal.reference_check && typeof proposal.reference_check === 'object');
}

function ptpInNotVerified(proposal) {
  return !ptpInStatusLine(proposal) && (Array.isArray(proposal.checks) ? proposal.checks : []).some(check => check?.status === 'not_verified' && check.id === 'ncci.ptp');
}

function referenceNote(proposal) {
  const checks = Array.isArray(proposal.checks) ? proposal.checks : [];
  const lines = [];
  if (proposal.status === 'excluded' && proposal.exclusion_reason) lines.push(`Excluded: ${proposal.exclusion_reason}`);
  if (proposal.supported === false) lines.push(`${proposal.family_label || 'This service'} is not covered by a profiled GI service family in this release — review required.`);
  for (const check of checks) if (check.status === 'fail' || check.status === 'warn') lines.push(`${lookup(CHECK_LABELS, check.status, '')} · ${check.label}: ${check.detail}`);
  // the ncci.ptp check is listed only where the status line does not state the limit (ptpInStatusLine)
  const stated = ptpInStatusLine(proposal);
  const notVerified = checks.filter(check => check.status === 'not_verified' && !(stated && check.id === 'ncci.ptp')).map(check => check.label);
  if (notVerified.length) lines.push(`Not verified: ${notVerified.join('; ')}.`);
  return lines.length ? `<div class="reference-note">${icon('info')}<span>${lines.map(escapeHtml).join('<br>')}</span></div>` : '';
}

// The engine's separate-lesions consideration ends by stating the limit again; where the card states it above (its
// status line, or its "Not verified" note) the line keeps the consideration and says only that no modifier is assigned.
const MODIFIER_PTP = 'NCCI edits are not connected; no modifier is assigned.';

function modifierNote(proposal) {
  const items = Array.isArray(proposal.modifier_considerations) ? proposal.modifier_considerations : [];
  const stated = ptpInStatusLine(proposal) || ptpInNotVerified(proposal);
  const shown = items.map(item => (stated && typeof item === 'string' && item.endsWith(MODIFIER_PTP) ? `${item.slice(0, -MODIFIER_PTP.length)}No modifier is assigned.` : item));
  return shown.length ? `<div class="reference-note">${icon('info')}<span>${escapeHtml(`Modifier considerations, never assigned automatically: ${shown.join(' ')}`)}</span></div>` : '';
}

function evidenceChips(proposal, layout) {
  // A support that was not checked gives no check result for the provider's passages either (refutation 7c8, reports-4).
  const checked = supportChecked(proposal);
  // Whose passages CPT Studio's source passages are: serviceOnlySupport (ownership-5); which of the provider's do not
  // show the coded act: passagesNotShowingTheAct, which the source panel's titles read too (display-6).
  const serviceOnly = serviceOnlySupport(proposal);
  const unrelated = new Set(checked && Array.isArray(proposal.support?.unrelated) ? proposal.support.unrelated : []);
  const notTheAct = passagesNotShowingTheAct(proposal);
  const provider = (proposal.evidence || []).map((evidence, index) => {
    const key = `${proposal.id}:${index}`;
    if (layout.unlocated.has(key)) return `<span class="evidence-chip unlocated">${icon('info')}<span>${escapeHtml(`“${evidence?.text ?? ''}” — not found at this position in the current revision, so it is not highlighted.`)}</span></span>`;
    const note = notTheAct.has(index) ? ' — cited by the provider; does not show the coded act' : unrelated.has(index) ? ' — cited by the provider' : '';
    return `<button type="button" class="evidence-chip" data-evidence="${escapeHtml(key)}">${icon('link')}<span>${escapeHtml(`“${evidence.text}”${note}`)}</span></button>`;
  });
  const source = (proposal.support?.source || []).map((evidence, index) => {
    const key = `${proposal.id}:s${index}`;
    if (layout.unlocated.has(key)) return '';
    return `<button type="button" class="evidence-chip" data-evidence="${escapeHtml(key)}">${icon('link')}<span>${escapeHtml(`“${evidence.text}” — selected from the source by CPT Studio${checked ? '' : '; not checked against the coded act'}`)}</span></button>`;
  });
  const sourceLabel = source.some(Boolean) ? groupLabel(!checked ? 'Passages of the documented service (not checked against the coded act)' : serviceOnly ? 'Source passages of the documented service' : 'Source passages that show the coded act') : '';
  return provider.join('') + sourceLabel + source.join('');
}

// A question leads in its own words; the engine's reason - the technical record of why it asks (cue strings, the names of
// its readings) - is kept whole behind a "Details" disclosure (refutation gi2, demo RC8). The reports print both. A
// question recorded without words leads with its reason, never with nothing.
function clarificationParts(clarification) {
  const question = typeof clarification.question === 'string' && clarification.question.trim() ? clarification.question : '';
  const reason = typeof clarification.reason === 'string' && clarification.reason.trim() ? clarification.reason : '';
  const details = question && reason ? `<details class="clarification-details"><summary>Details</summary><span class="clarification-reason">${escapeHtml(reason)}</span></details>` : '';
  return { lead: question || reason, details };
}

function clarificationQuestion(clarification, doc) {
  const { lead, details } = clarificationParts(clarification);
  const candidates = candidateAnswers(clarification, doc);
  const answer = canEdit(doc) ? `${details || candidates ? '' : '<br>'}<button type="button" class="button secondary" data-action="addendum" data-clarification="${escapeHtml(clarification.id)}">Answer with an addendum</button>` : '';
  return `<div class="clarification-question"><strong>Clarification needed</strong><br>${escapeHtml(lead)}${details}${candidates}${answer}</div>`;
}

// Quoted passages of the document (a candidate's or a confirmation's spans), each with its page; one not at its
// position in the current revision is flagged, never passed off as found. ``sentences``: a candidate's (HARNESS.md
// 12.5), the readers' whole sentence of each span, in its order - a span that is a slice of a longer sentence is shown
// with that sentence, so a hedge around it is never hidden behind a Verified badge (refutation round 2, EV2-1); one whose
// sentence is not served exactly says so. A payload that serves no sentences (a confirmation) is quoted as before.
function quotedSpans(spans, exact, sentences) {
  return objects(spans).map((span, index) => {
    const page = Number.isInteger(span.page) ? ` (page ${span.page})` : '';
    const quote = `“${textValue(span.text)}”${page}`;
    if (!exact(span)) return `${quote} — not found at this position in the current revision`;
    const whole = spanSentence(span, index, sentences, exact);
    if (whole === null) return quote;
    return whole === '' ? `${quote} — its whole sentence is not shown: read it in the document before confirming` : `${quote} — a part of the sentence “${whole}”`;
  });
}

// The readers' whole sentence of an exact span of a candidate (candidate.sentences[index]): null when the span is that
// whole sentence, or when no sentences are served at all; '' when the served sentence is not an exact passage holding
// the span (fail closed: it cannot be shown as the span's sentence); otherwise the sentence's text.
function spanSentence(span, index, sentences, exact) {
  if (!Array.isArray(sentences)) return null;
  const sentence = sentences[index];
  if (!sentence || typeof sentence !== 'object' || !exact(sentence) || !Number.isInteger(sentence.start) || !Number.isInteger(sentence.end)
      || sentence.start > span.start || span.end > sentence.end) return '';
  return sentence.start === span.start && sentence.end === span.end ? null : textValue(sentence.text);
}

// A reviewer's confirmation of a question (clarification.confirmation, HARNESS.md 11.3): who located the passage and
// who confirmed it, the value and passage, the attestation recorded and when. A confirmed fact, never a decision on a
// code.
function confirmedAnswer(confirmation, exact) {
  const value = textValue(confirmation.value);
  const when = [formatTimestamp(confirmation.created_at), confirmation.confirmed_by_kind === 'agent' ? 'agent-executed synthetic review — not clinical approval' : ''].filter(Boolean).join(' · ');
  const lines = [...quotedSpans(confirmation.spans, exact), `Attestation recorded: ${textValue(confirmation.attestation) || 'none recorded'}`,
    [when, 'A confirmed finding is not a decision: each code still needs its own.'].filter(Boolean).join(' · ')];
  return `<div class="confirmed-answer">${icon('shield')}<div><strong>${escapeHtml(`${confirmedFrom(confirmation)}: ${value || 'no value recorded'}`)}</strong>${lines.map(line => `<p>${escapeHtml(line)}</p>`).join('')}</div></div>`;
}

// The Confirm action of a verified candidate (HARNESS.md 11.3, 12.5): the exact attestation the candidate is served
// with, which the reviewer ticks before the confirmation is recorded; that same served sentence is what is sent.
function confirmControl(candidate, clarificationId) {
  return `<details class="confirm-finding"><summary>Confirm this answer</summary><label class="check-label"><input type="checkbox" data-attest><span>${escapeHtml(textValue(candidate.attestation))}</span></label><p class="form-error" role="alert" hidden></p><button type="button" class="button primary" data-action="confirm-finding" data-clarification="${escapeHtml(clarificationId)}" data-confirm="${escapeHtml(textValue(candidate.id))}" disabled>Record my confirmation ${icon('check')}</button><small class="check-source">Your confirmation is recorded with your name and the time, and it answers only this question. It is not an approval: each code still needs its own decision.</small></details>`;
}

// One candidate answer (HARNESS.md 12.5): its value in CPT Studio's own words, the passage quoted from the document,
// who located it and in which phase, whether it is verified (and why not). Only a verified candidate whose passages are
// at their positions can be confirmed, and only by a member the API allows (permissions.can_confirm).
function candidateAnswer(candidate, clarificationId, confirmable, exact) {
  const verified = candidate.verified === true;
  const spans = objects(candidate.spans);
  const quotes = quotedSpans(spans, exact, candidate.sentences);
  const value = textValue(candidate.value).trim();
  const checked = lookup(VERIFIED_CHECKS, candidate.fact, 'it passes the consistency check for this fact');
  const why = verified ? `Verified: its passage is an exact slice of the document, ${VERIFIED_SECTIONS}, and ${checked}. It is still only a candidate: read the passage before confirming it.`
    : `Not verified, so it cannot be confirmed: ${textValue(candidate.why).trim() || 'no reason was recorded.'}`;
  // fail closed: a span whose whole sentence cannot be shown is never confirmed from this page
  const shown = spans.every((span, index) => spanSentence(span, index, candidate.sentences, exact) !== '');
  const action = confirmable && verified && spans.length > 0 && spans.every(exact) && shown && textValue(candidate.attestation) ? confirmControl(candidate, clarificationId) : '';
  return `<li class="candidate-answer" data-candidate="${escapeHtml(textValue(candidate.id))}" data-verified="${verified}"><span class="participant-head"><strong>${escapeHtml(value || 'No value CPT Studio can state')}</strong>${verified ? badge('green', 'Verified') : badge('amber', 'Not verified')}</span>${(quotes.length ? quotes : ['No passage is cited.']).map(quote => `<p class="candidate-quote">${escapeHtml(quote)}</p>`).join('')}<small class="check-source">${escapeHtml(locatedBy(candidate))}</small><small class="check-source">${escapeHtml(why)}</small>${action}</li>`;
}

// An open question's candidate answers from the participants' located passages and its confirmation (HARNESS.md 11.3,
// 12.5, 12.6), drawn only where the API allows this member to confirm one (permissions.can_confirm true: the dormant
// confirmation path, never this release); '' otherwise, and for a question served with neither (a payload before
// harness@2, a Corti-only encounter, an assess #1). Refutation round 4 (HARNESS.md 12.10 as amended, the session's
// D8): with no confirmation offered nothing is drawn here, whatever a payload carries - round 3 drew each candidate as
// the participants' located passage, "Their answer: <value>", where the value was CPT Studio's own inference from a
// reading, never a participant's answer to the question. Agreement is never shown as confirmation: a candidate several
// participants located is one candidate naming them all.
function candidateAnswers(clarification, doc) {
  if (doc.permissions?.can_confirm !== true) return '';
  const candidates = objects(clarification.candidates);
  const confirmation = clarification.confirmation && typeof clarification.confirmation === 'object' ? clarification.confirmation : null;
  if (!candidates.length && !confirmation) return '';
  const exact = exactIn(doc.revision?.text);
  const id = textValue(clarification.id);
  const confirmable = !confirmation && !doc.pipeline?.busy;
  const items = candidates.map(candidate => candidateAnswer(candidate, id, confirmable, exact)).join('');
  const list = candidates.length ? `${groupLabel(`Candidate answers from the participants' located passages · ${candidates.length}`)}<ul class="candidate-list">${items}</ul>` : '';
  return `<div class="candidate-answers" data-question="${escapeHtml(id)}"${confirmation ? ` data-confirmation="${escapeHtml(textValue(confirmation.id))}"` : ''}>${confirmation ? confirmedAnswer(confirmation, exact) : ''}${list}<p class="harness-note">${escapeHtml(CANDIDATE_NOTE)}</p></div>`;
}

// A code's CMS reference check (HARNESS.md I4: PTP is always "not verified"), stating the PTP limit exactly once: the
// API's detail ends with its own sentence saying the NCCI procedure-to-procedure edits are not connected (review.
// PTP_NOT_CONNECTED), so the page's parenthetical is added only where the detail does not say it (refutation round 2,
// FG2-5: every real card stated it twice).
function referenceCheckText(check) {
  const said = lookup(REFERENCE_CHECK_LABELS, check?.state, 'not verified');
  const detail = typeof check?.detail === 'string' && check.detail.trim() ? ` — ${check.detail.trim()}` : '';
  const stated = /procedure-to-procedure edits are not connected/i.test(detail);
  return `${said}${detail}${stated ? '' : ' (NCCI procedure-to-procedure edits not verified: not connected)'}`;
}

function decisionWords(proposal) {
  const stateName = lookup(DECISION_WORDS, proposal.decision_state, null) ? proposal.decision_state : 'undecided';
  const decision = stateName === 'undecided' ? null : proposal.decision;
  const by = decision?.reviewer ? ` by ${decision.reviewer}` : '';
  const agent = decision?.reviewer_kind === 'agent' ? ' (agent-executed synthetic review — not clinical approval)' : '';
  return DECISION_WORDS[stateName].replace('{by}', () => by) + agent;
}

// A code's three statuses, kept apart (HARNESS.md I4): who proposed it, what the CMS reference checks found (the
// procedure-to-procedure edits are not connected, so never verified) and the reviewer's decision. Agreement between
// participants and passing checks approve nothing. '' for a proposal served before the harness existed.
function codeStatusLines(proposal) {
  const proposers = Array.isArray(proposal.proposed_by) ? proposal.proposed_by.filter(name => typeof name === 'string' && name) : null;
  const check = proposal.reference_check && typeof proposal.reference_check === 'object' ? proposal.reference_check : null;
  if (!proposers && !check) return '';
  const listed = listedText(proposal.listed_by);
  const lines = [
    ['Proposed by', proposers?.length ? proposerText(proposal, proposers) : listed ? `no participant; ${listed}` : 'not recorded'],
    ['CMS reference checks', referenceCheckText(check)],
    ['Reviewer decision', decisionWords(proposal)],
  ];
  return `<ul class="code-status-lines" aria-label="Status of this code">${lines.map(([name, value]) => `<li><b>${escapeHtml(name)}:</b> ${escapeHtml(value)}</li>`).join('')}</ul>`;
}

// How Corti stands to a code it is not a proposer of (proposal.corti_relation, HARNESS.md 11.4), in the engine's own
// words: "Corti did not propose this code" only when Corti has no entry for the code at all (refutation round 2,
// truth-6: it was said whenever Corti was not a proposer, beside Corti's own excluded selection of the code). A code
// Corti listed without selecting it, or its second review listed without adding it, is said to be listed, in words
// that name no one role - the record gives the engine none - and its Alternatives row says which (refutation round 3,
// truth-5: an alternative to another code was said to be listed "only as a candidate").
const CORTI_RELATIONS = {
  selected_without_exact_passage: 'Corti also selected this code, with no exact passage; it is listed apart, excluded.',
  selected_apart: 'Corti also selected this code; its selection is listed apart.',
  candidate: 'Corti listed this code as a candidate or an alternative, not selected; see Alternatives.',
  second_review: 'Corti\'s second review also listed this code without adding it as a proposal; see Alternatives.',
  none: 'Corti did not propose this code.',
};

// Who proposed a code, each participant with the phase it first proposed it in where the API serves one (HARNESS.md
// 11.1: after peer review is never called independent), then how Corti stands to a code it did not propose (11.4) -
// nothing about Corti where the API serves no relation, since the record would have to support it.
function proposerText(proposal, proposers) {
  const phases = proposalPhases(proposal);
  const named = proposers.map(name => {
    const phase = Object.hasOwn(phases, name) ? lookup(PROPOSED_PHASES, phases[name], '') : '';
    return `${lookup(PARTICIPANT_LABELS, name, name)}${phase ? ` (${phase})` : ''}`;
  }).join(', ');
  const listed = listedText(proposal.listed_by, true);
  const corti = proposers.includes('corti') ? '' : lookup(CORTI_RELATIONS, proposal.corti_relation, '');
  return [named, listed, corti].filter(Boolean).join('; ');
}

// The participants the API serves as having only listed a participant's alternative's code (listed_by: no quote of
// theirs was found verbatim in the document, so they did not propose it; refutation round 5, the session's D12), named
// apart from its proposers - "listed by Fable with no quote found verbatim in the document, so not proposed", and "by
// Fable" after it where others proposed the code - never as one of them, and with no proposer as "no participant",
// never "none" (Corti may have a row of its own for the code); '' when it serves none. Only Astra and Fable are named,
// as review.listed_by serves only them: a name the page does not know, or Corti, is never named as having listed the
// code (refutation round 6, falsegreen-4: 'mallory' and 'corti' were named as served).
function listedText(listedBy, apart = false) {
  const names = joinWords(strings(listedBy).filter(name => name === 'astra' || name === 'fable').map(name => PARTICIPANT_LABELS[name]));
  return names ? `listed by ${names} with no quote found verbatim in the document, so not proposed${apart ? ` by ${names}` : ''}` : '';
}

// The reviewer-confirmed findings this code's checks read (proposal.confirmed, HARNESS.md 11.3): each a fact a reviewer
// confirmed from a participant's located passage - never the reader's own reading and never a decision on the code,
// whose own decision line says that apart. '' for a proposal that read none.
function confirmedFacts(proposal, doc) {
  const ids = strings(proposal.confirmed);
  if (!ids.length) return '';
  const exact = exactIn(doc.revision?.text);
  const known = [...objects(doc.confirmations), ...objects(doc.clarifications).map(item => item.confirmation).filter(item => item && typeof item === 'object')];
  const lines = ids.map(id => {
    const confirmation = known.find(item => item.id === id);
    if (!confirmation) return `A confirmed finding that is not listed for this revision (${id}).`;
    const fact = lookup(FINDING_FACTS, confirmation.fact, textValue(confirmation.fact).replace(/_/g, ' ') || 'Fact');
    const quotes = quotedSpans(confirmation.spans, exact);
    return `${fact}: ${textValue(confirmation.value) || 'no value recorded'} — ${confirmedFrom(confirmation).replace(/^C/, 'c')}${quotes.length ? ` · ${quotes.join('; ')}` : ''}`;
  });
  return `<div class="confirmed-fact">${icon('shield')}<span><strong>Confirmed finding, not a decision</strong>${lines.map(line => `<br>${escapeHtml(line)}`).join('')}</span></div>`;
}

// A participant's position on a code, with the passage it quoted: the API's quote is its first LOCATED quote, an exact
// slice of the revision (jobs._first_located, I7), so it is the document's own text and is shown as it is, as the trace
// shows a located quote (refutation round 2, IR2-4: a passage was withheld for the plural mark the document wrote).
function positionText(name, position) {
  const detail = participantText(position?.detail);
  const quote = typeof position?.quote === 'string' ? position.quote.trim() : '';
  const said = `${lookup(PARTICIPANT_LABELS, name, name)} ${lookup(POSITION_WORDS, position?.position, 'took a position that was not recorded')}${detail ? `: ${detail}` : ''}`;
  return quote ? `${said} — “${quote}”` : sentence(said);
}

// What Astra and Fable each said about this code (participant_positions; {} when none is configured): proposed it, did
// not, advised not to code it (with its reason and the passage it quoted), or gave no reading. A position never decides
// the code's status (I2), agreement never promotes it (I3), and a contradiction is shown, never voted on.
// harness@2 (heading): the positions are those of the frozen first readings, whatever followed in peer review.
function participantPositions(proposal, heading = 'What the participants said') {
  const positions = proposal.participant_positions;
  if (!positions || typeof positions !== 'object' || Array.isArray(positions)) return '';
  const rank = name => (Object.hasOwn(PARTICIPANT_LABELS, name) ? Object.keys(PARTICIPANT_LABELS).indexOf(name) : 99);
  const names = Object.keys(positions).filter(name => positions[name] && typeof positions[name] === 'object').sort((a, b) => rank(a) - rank(b));
  if (!names.length) return '';
  return `<div class="evidence-section participant-positions">${groupLabel(heading)}${names.map(name => `<p class="harness-note">${escapeHtml(positionText(name, positions[name]))}</p>`).join('')}</div>`;
}

// The references the participants retrieved with their own tool calls and those they say they used, for this code
// (harness.participants[].references and .peer_references, HARNESS.md 11.2): each by participant and phase, a used one
// marked retrieved or "cited, not retrieved" by CPT Studio's check against that same run. A fact names its code, so
// only this code's are listed; a policy passage names none, so it is listed on every card. Kept apart from each other
// and from the reconciliation's retrieval (retrievalSection), never merged. '' for a payload without harness@2.
function referenceLists(proposal, doc) {
  if (!harness2(doc)) return '';
  const retrieved = [];
  const used = [];
  for (const row of objects(doc.harness.participants)) {
    for (const [field, phase] of [['references', 'first reading'], ['peer_references', 'peer review']]) {
      const refs = row[field] && typeof row[field] === 'object' ? row[field] : {};
      // a reuse's references are the tool calls of the retained run it reuses (refutation round 2, truth-13)
      const reused = Boolean(textValue(refs.reused_from));
      const who = `${lookup(PARTICIPANT_LABELS, row.name, textValue(row.name) || 'Participant')} · ${phase}${reused ? ' (the retained run it reuses)' : ''}`;
      for (const item of objects(refs.retrieved).filter(entry => refConcerns(entry.ref, proposal.code))) {
        const window = textValue(item.effective_start) && textValue(item.effective_end) ? `effective ${formatDate(item.effective_start) || item.effective_start} – ${formatDate(item.effective_end) || item.effective_end}` : '';
        const passage = textValue(item.ref).startsWith('fact:') ? '' : ' (a policy passage, not tied to one code)';
        retrieved.push(`<li><b>${escapeHtml(who)}:</b> ${escapeHtml(`${textValue(item.ref)}${passage}`)}<small class="check-source">${escapeHtml([textValue(item.tool), textValue(item.source_key), textValue(item.release), window].filter(Boolean).join(' · '))}</small></li>`);
      }
      for (const item of objects(refs.used).filter(entry => refConcerns(entry.ref, proposal.code, entry.retrieved === true))) {
        const checked = reused
          ? (item.retrieved === true ? 'retrieved by the tool calls of the retained run this run reuses' : 'cited, not retrieved: the tool calls of the retained run this run reuses never returned it')
          : (item.retrieved === true ? 'retrieved by its own tool calls in this run' : 'cited, not retrieved: its own tool calls in this run never returned it');
        // a cited reference is the participant's own text: shown only as a short id, otherwise by its length
        // (shownReference); its use is free text, withheld where it reads like a CPT descriptor
        const use = participantText(item.use);
        used.push(`<li><b>${escapeHtml(who)}:</b> ${escapeHtml(`${participantText(shownReference(item)) || 'a reference not named'} — ${checked}`)}${use ? `<small class="check-source">${escapeHtml(`Its use: “${use}”`)}</small>` : ''}</li>`);
      }
    }
  }
  const list = (items, empty) => (items.length ? `<ul class="reference-facts">${items.join('')}</ul>` : `<p class="harness-note">${escapeHtml(empty)}</p>`);
  return `<div class="evidence-section reference-lists">${groupLabel('References the participants retrieved (their own tool calls)')}${list(retrieved, 'No participant retrieved a reference for this code.')}${groupLabel('References the participants say they used')}${list(used, 'No participant cites a reference for this code.')}</div>`;
}

function textValue(value) {
  if (typeof value === 'string') return value;
  return typeof value === 'number' || typeof value === 'boolean' ? String(value) : '';
}

// Where a retrieved fact or passage comes from: its source key, release, section and page.
function retrievedFrom(item) {
  const page = textValue(item.page);
  return [textValue(item.source_key), textValue(item.release), textValue(item.section), page ? `page ${page}` : ''].filter(Boolean).join(' · ');
}

// The CMS reference facts and passages retrieved for this code (proposal.retrieval, HARNESS.md 5): each fact with its
// source and release, and each passage - verbatim CMS text - behind its own disclosure. '' for a proposal served before
// the harness existed.
// harness@2 (reconciliation): named as the reconciliation's own retrieval beside the participants' (HARNESS.md 11.2).
// ``failed``: the assessment's retrieval failed (harness.reference_validation), so a code with nothing retrieved says that,
// never that its lookup found nothing.
function retrievalSection(proposal, reconciliation = false, failed = false) {
  if (!Array.isArray(proposal.retrieval)) return '';
  const items = proposal.retrieval.filter(item => item && typeof item === 'object');
  const facts = items.filter(item => item.kind === 'fact');
  const passages = items.filter(item => item.kind === 'passage');
  const heading = groupLabel(reconciliation ? 'CMS reference facts and passages retrieved by the reconciliation' : 'CMS reference facts and passages');
  if (!facts.length && !passages.length) return `<div class="evidence-section reference-retrieval">${heading}<p class="harness-note">${escapeHtml(failed ? RETRIEVAL_FAILED : 'No CMS reference fact or passage was retrieved for this code.')}</p></div>`;
  const factList = facts.length ? `<ul class="reference-facts">${facts.map(fact => `<li><b>${escapeHtml(textValue(fact.label) || textValue(fact.field) || 'Fact')}:</b> ${escapeHtml(textValue(fact.value) || 'not recorded')}<small class="check-source">${escapeHtml(retrievedFrom(fact))}</small></li>`).join('')}</ul>` : '';
  const passageList = passages.map(passage => {
    const page = textValue(passage.page);
    const title = [textValue(passage.label) || textValue(passage.section) || 'CMS passage', page ? `page ${page}` : ''].filter(Boolean).join(' · ');
    return `<details class="reference-passage"><summary>${escapeHtml(title)}</summary><p>${escapeHtml(textValue(passage.text))}</p><small class="check-source">${escapeHtml(retrievedFrom(passage))}</small></details>`;
  }).join('');
  return `<div class="evidence-section reference-retrieval">${heading}${factList}${passageList}</div>`;
}

function codeCard(proposal, doc, layout) {
  const count = (proposal.evidence || []).length;
  const units = Number.isInteger(proposal.units) && proposal.units > 1 ? `Units: ${proposal.units} · ` : '';
  const second = proposal.support?.origin === 'second_review' ? `<span class="small-badge">Second review</span>` : '';
  // HARNESS.md P-ADMIT (2026-11-05): a proposal an independent participant's first reading made, which CPT Studio's
  // readers admitted, says so to the operator; customers are never shown who proposed a code (studio/customer_api.py)
  const admitted = proposal.bucket === 'selected' && proposal.support?.origin === 'participant'
    ? '<span class="small-badge">Independent participant</span>' : '';
  // harness@2: a code first proposed in peer review says so (HARNESS.md 11.1); the first readings' positions are named
  // as such, and the three kinds of references are kept apart (11.2)
  const peer = peerPhaseOnly(proposal) ? '<span class="small-badge">Proposed after peer review</span>' : '';
  const phased = harness2(doc);
  const positions = phased ? participantPositions(proposal, 'What the participants said in their first readings') : participantPositions(proposal);
  return `<article class="code-card" id="card-${escapeHtml(proposal.id)}" tabindex="-1"><div class="code-card-main"><div class="code-card-top"><span class="code-category">${escapeHtml(proposal.eyebrow || proposal.family_label || '')}</span>${second}${admitted}${peer}${proposalBadge(proposal)}</div><strong class="code-number">${escapeHtml(proposal.code)}</strong><h3>Description withheld</h3><span class="code-short-note">${escapeHtml(units + (proposal.descriptor?.label || 'No licensed CPT descriptor is connected.'))}</span>${codeStatusLines(proposal)}${confirmedFacts(proposal, doc)}${proposal.rationale ? `<p class="code-rationale">${escapeHtml(proposal.rationale)}</p>` : ''}${clarificationsFor(proposal, doc).map(item => clarificationQuestion(item, doc)).join('')}</div><div class="evidence-section"><div class="evidence-label">${icon('link')}${escapeHtml(passagesLabel(count))}</div>${evidenceChips(proposal, layout)}${referenceNote(proposal)}${modifierNote(proposal)}</div>${positions}${referenceLists(proposal, doc)}${retrievalSection(proposal, phased, doc?.harness?.reference_validation?.state === 'failed')}${decisionLine(proposal)}${cardActions(proposal)}</article>`;
}

function clarificationCard(clarification, doc) {
  const family = clarification.family ? familyLabel(doc, clarification.family) : '';
  const answer = canEdit(doc) ? `<button type="button" class="button primary" data-action="addendum" data-clarification="${escapeHtml(clarification.id)}">Answer with an addendum ${icon('arrow')}</button>` : '';
  const { lead, details } = clarificationParts(clarification);
  return `<div class="clarification-card"><span class="clarification-icon">${icon('help')}</span><span class="clarification-eyebrow">${escapeHtml(family ? `Clarification needed · ${family}` : 'Clarification needed')}</span><h3 class="clarification-lead">${escapeHtml(lead)}</h3>${details}${candidateAnswers(clarification, doc)}${answer}</div>`;
}

// What a reviewer did with an excluded candidate, or that a documentation check's exclusion still needs a decision.
function candidateDecision(proposal) {
  const who = proposal.decision?.reviewer || 'a reviewer whose name was not recorded';
  if (proposal.decision_state === 'exclusion_confirmed') return `Exclusion confirmed by ${who}.`;
  if (proposal.decision_state === 'reinstated') {
    // The code's own gate, which the server reads the same for every member, says whether it can be approved; the
    // member's action list only says what this member may do (round 6, bypass:3). A withheld code names the gate
    // (round 5, bypass:6).
    const withheld = typeof proposal.approve_withheld_by === 'string' ? proposal.approve_withheld_by : '';
    if (!withheld) {
      const allowed = Array.isArray(proposal.allowed_actions) ? proposal.allowed_actions : [];
      return allowed.includes('approve') ? `Reinstated for review by ${who}; approve or reject it.` : `Reinstated for review by ${who}; a reviewer approves or rejects it.`;
    }
    const checks = Array.isArray(proposal.checks) ? proposal.checks : [];
    const gate = checks.find(check => check.id === withheld);
    return [`Reinstated for review by ${who}. It cannot be approved yet: it can be rejected, the reinstatement undone, or the missing documentation added as an addendum.`, gate?.detail || ''].filter(Boolean).join(' ');
  }
  if (proposal.decision_state === 'approved' || proposal.decision_state === 'rejected') return `${lookup(DECISION_TITLES, proposal.decision?.action, 'Decided')} by ${who} after reinstatement.`;
  if (proposal.bucket === 'excluded' && proposal.reinstatable) return 'Needs your decision: confirm the exclusion or reinstate the code.';
  return '';
}

function candidateItem(proposal, fallback, doc, extra = '') {
  const allowed = Array.isArray(proposal.allowed_actions) ? proposal.allowed_actions : [];
  // Every action the server allows, in the card order: a reinstated code is approved or rejected here too.
  const decisions = ACTION_BUTTONS.filter(([name]) => allowed.includes(name)).map(([name]) => decisionButton(name, proposal));
  // A reinstated code whose gate withholds approve is told to add the missing documentation, so the row offers the
  // addendum itself; POST /addenda needs no clarification (round 6, bypass:1).
  const withheld = proposal.decision_state === 'reinstated' && typeof proposal.approve_withheld_by === 'string' && proposal.approve_withheld_by;
  const addendum = withheld && doc && canEdit(doc) ? ['<button type="button" class="button secondary" data-action="addendum">Add the missing documentation (addendum)</button>'] : [];
  const actions = decisions.concat(addendum).join(' ');
  // A code the bounded second review listed says so here, as the code card's badge, the TXT ("second-review
  // alternative") and the CSV (proposal_origin) do (eus2 F4: its alternatives were drawn like the primary's).
  const origin = proposal.support?.origin === 'second_review' ? ' · from the second review' : peerPhaseOnly(proposal) ? ' · proposed after peer review' : '';
  return checkItem('muted', 'info', `${proposal.code} · ${proposal.family_label || proposal.family || ''}${origin}`, [proposal.exclusion_reason || fallback, candidateDecision(proposal)].filter(Boolean).join(' '), actions + extra);
}

function candidateSection(title, proposals, fallback, doc) {
  if (!proposals.length) return '';
  return `${sectionHeading(title, proposals.length)}<div class="check-list-card">${proposals.map(proposal => candidateItem(proposal, fallback, doc)).join('')}</div>`;
}

// Informational candidates (the alternative bucket) by the served rows alone (refutation gi2, demo RC7: every provider
// candidate was one flat list, a CABG code beside the colonoscopy's own alternatives): those of the GI family of a service
// the document documents (assessment.services, whatever its status) whose code is in CPT scope (its scope.cpt check did not
// fail), and the rest - outside the documented services, or not a CPT code. Every candidate is in exactly one group. null
// when the assessment recorded no documented-service reading (made before it existed): the list is drawn ungrouped.
function candidateGroups(assessment) {
  const services = assessment?.services?.services;
  if (!Array.isArray(services)) return null;
  const families = new Set(services.map(service => service?.family).filter(family => typeof family === 'string' && family));
  const inScope = proposal => !(Array.isArray(proposal.checks) ? proposal.checks : []).some(check => check?.id === 'scope.cpt' && check.status === 'fail');
  const same = [];
  const other = [];
  for (const proposal of proposalsIn(assessment, 'alternative')) (families.has(proposal.family) && inScope(proposal) ? same : other).push(proposal);
  return { same, other };
}

// Whether a passage is at its position in the revision text (code points, as the API counts them).
function exactIn(text) {
  const source = String(text || '');
  const offsets = codeUnitOffsets(source);
  const length = offsets ? offsets.length - 1 : source.length;
  const unit = point => (offsets ? offsets[point] : point);
  return span => isExactSpan(source, span, length, unit);
}

// The passages a candidate cites, quoted on expand; one not at its position in the current revision is flagged as an
// evidence chip flags it, never passed off as found. They are not marked in the source: a candidate is never evidence.
// The engine keeps only a candidate's exact passages, so none kept is not "none cited".
function candidatePassages(proposal, exact) {
  const spans = Array.isArray(proposal.evidence) ? proposal.evidence : [];
  if (!spans.length) return '<small class="check-source">No exact source passage is linked to this candidate.</small>';
  const quotes = spans.map(span => `<p>${escapeHtml(`“${span?.text ?? ''}”${exact(span) ? '' : ' — not found at this position in the current revision'}`)}</p>`).join('');
  return `<details class="candidate-passages"><summary>${spans.length === 1 ? 'Cited passage' : `Cited passages (${spans.length})`}</summary>${quotes}</details>`;
}

const ALTERNATIVE_NOTE = 'Offered by the provider as an alternative and not selected. Alternatives cannot be approved.';

// The alternatives, never selectable: the candidates of a documented service's family first, the rest collapsed with
// their count. Nothing is dropped or hidden beyond a disclosure, and no candidate gains an action the server does not
// allow (none for an alternative). The reports list every candidate as before.
function alternativesSection(doc) {
  const alternatives = proposalsIn(doc.assessment, 'alternative');
  if (!alternatives.length) return '';
  const exact = exactIn(doc.revision?.text);
  const items = list => list.map(proposal => candidateItem(proposal, ALTERNATIVE_NOTE, doc, candidatePassages(proposal, exact))).join('');
  const heading = sectionHeading('Alternatives (never selectable)', alternatives.length);
  const groups = candidateGroups(doc.assessment);
  if (!groups) return `${heading}<div class="check-list-card">${items(alternatives)}</div>`;
  const same = groups.same.length ? `<div class="check-list-card">${groupLabel(`Same GI family as a documented service · ${groups.same.length}`)}${items(groups.same)}</div>` : '';
  const other = groups.other.length ? `<details class="check-list-card candidate-group"><summary>${escapeHtml(`Outside the documented services or not a CPT code · ${groups.other.length}`)}</summary>${items(groups.other)}</details>` : '';
  return `${heading}<div class="card-stack">${same}${other}</div>`;
}

const SERVICE_STATUS_LABELS = { performed: 'performed', incomplete: 'performed, incomplete', planned: 'planned', historical: 'historical', cancelled: 'cancelled', negated: 'documented as not performed', uncertain: 'not established' };
const CODING_TONES = { incomplete: 'pending', pending_review: '', reviewed: '', not_established: 'muted' };

// The encounter's coding completeness, kept apart from whether a proposal is ready for review.
function codingBanner(doc) {
  const coding = doc.coding;
  if (!coding || !coding.statement) return '';
  // pending_review is also a decided set waiting on a context change or processing: its title never says a proposal
  // is left to review, and the statement says what is missing (refutation 7c8, reports-3).
  const title = lookup({ incomplete: 'Coding for this encounter is incomplete', pending_review: 'Every documented service has a proposal; the review is not complete', reviewed: 'Every documented service has a reviewed decision', not_established: 'Coding completeness not established' }, coding.state, 'Coding completeness');
  return `<div class="check-list-card">${checkItem(lookup(CODING_TONES, coding.state, 'pending'), coding.state === 'incomplete' ? 'info' : 'shield', title, coding.statement)}</div>`;
}

function serviceTitle(service, doc) {
  const parts = [familyLabel(doc, service.family) || service.kind, lookup(SERVICE_STATUS_LABELS, service.status, service.status)];
  if (service.completion && service.completion !== 'unknown' && ['performed', 'incomplete'].includes(service.status)) parts.push(`${service.completion} examination${service.extent ? ` (${service.extent})` : ''}`);
  if (service.intent) parts.push(service.intent);
  return parts.filter(Boolean).join(' · ');
}

function documentedServices(doc) {
  const assessment = doc.assessment || {};
  const inventory = assessment.services || {};
  const services = Array.isArray(inventory.services) ? inventory.services : [];
  if (!services.length) return '';
  const completeness = assessment.completeness || {};
  const unresolved = Array.isArray(completeness.unresolved_items) ? completeness.unresolved_items : [];
  const bundled = Array.isArray(completeness.bundled) ? completeness.bundled : [];
  const covered = completeness.covered || {};
  // A code the reviewer rejected accounts for nothing in the review: shown as rejected (refutation r1, report-6).
  const rejected = new Set((assessment.proposals || []).filter(proposal => proposal.bucket !== 'alternative' && proposal.decision_state === 'rejected').map(proposal => proposal.code));
  const conflicts = Array.isArray(inventory.conflicts) ? inventory.conflicts : [];
  const items = services.map(service => {
    const lines = [];
    const done = ['performed', 'incomplete'].includes(service.status);
    const acts = (service.acts || []).filter(act => act.status === 'performed' && ['physician', 'unknown'].includes(act.role));
    if (done && acts.length) lines.push(`Acts documented as done: ${[...new Set(acts.map(act => act.kind.replace(/_/g, ' ') + (act.anatomy?.length ? ` (${act.anatomy.join(', ')})` : '')))].join('; ')}.`);
    const codes = done && Array.isArray(covered[service.id]) ? covered[service.id] : [];
    const kept = codes.filter(code => !rejected.has(code));
    const dropped = codes.filter(code => rejected.has(code));
    if (kept.length) lines.push(`Accounted for by: ${kept.join(', ')}.`);
    if (dropped.length) lines.push(`Rejected by the reviewer: ${dropped.join(', ')}${kept.length ? '' : '; no other selected code accounts for this service'}.`);
    // Worded from the inclusion rule as the assessment recorded it (included_by: the selected codes of that service that
    // include this examination), never from whether the service is listed: an EGD with a code of its own beside an EUS
    // code that includes none was said to be included by it (refutation P2RA, EUS lens 1; refutation p2, reports2:0).
    // Nothing recorded (an earlier assessment, a reading that decided nothing): the reading alone is stated.
    // A code the reviewer rejected includes nothing in the review either (refutation P2FR, EUS-SECOND).
    const includedBy = completeness.included_by && typeof completeness.included_by === 'object' && Array.isArray(completeness.included_by[service.id]) ? completeness.included_by[service.id].filter(code => !rejected.has(code)) : null;
    if (done && service.included_in) lines.push(includedBy === null
      ? `Read as part of ${service.included_in}.`
      : includedBy.length
        ? `Included in ${service.included_in}: that service's code includes this examination, so no code of its own is asked.`
        : `Read as part of ${service.included_in}, but no selected code of that service includes this examination.`);
    for (const item of unresolved.filter(entry => entry.service === service.id)) lines.push(`Unresolved: ${item.label}. No code is added for it and no alternative is promoted.`);
    for (const item of bundled.filter(entry => entry.service === service.id)) lines.push(`Not separately reported: ${item.label} — ${item.why}`);
    for (const conflict of conflicts.filter(entry => entry.service === service.id)) {
      const sides = (conflict.sides || []).map(side => `${side.role} entry: ${side.status}${side.evidence?.[0]?.text ? ` (“${side.evidence[0].text.replace(/\s+/g, ' ').slice(0, 120)}”)` : ''}`).join('; ');
      lines.push(`Conflict on ${conflict.subject.replace(/_/g, ' ')}: ${sides}. Both are kept; neither is chosen.`);
    }
    const tone = !done ? 'muted' : unresolved.some(entry => entry.service === service.id) || conflicts.some(entry => entry.service === service.id) ? 'pending' : '';
    return checkItem(tone, done ? 'circle-check' : 'info', serviceTitle(service, doc), lines.join(' '));
  });
  const attributions = (inventory.attributions || []).map(item => item.role);
  if (attributions.length) items.push(checkItem('muted', 'info', 'Another provider\'s services', `The document attributes ${attributions.join(', ')} services to their own providers; they are never coded for the performing physician.`));
  // The API serves the reconciliation as the review leaves it: a code the reviewer reinstated counts as a selected one
  // (refutation P2FR, EUS-SECOND), and that is said.
  const reinstated = reinstatedCounted(doc);
  if (reinstated.length) items.push(checkItem('muted', 'info', 'Counted with the reviewer\'s reinstatement', `The documented services are reconciled with ${reinstated.join(', ')}, which the reviewer reinstated, counted as selected.`));
  return `${sectionHeading('Documented services', services.length)}<div class="check-list-card">${items.join('')}${secondReviewItem(doc)}</div>`;
}

// The codes a reviewer reinstated that the served reconciliation counts (completeness.reinstated).
function reinstatedCounted(doc) {
  const reinstated = doc?.assessment?.completeness?.reinstated;
  return Array.isArray(reinstated) ? reinstated.filter(code => typeof code === 'string') : [];
}

// The second review a reviewer asked for whose own outcome is not recorded yet: the current revision's latest review2
// stage, when no assessment came after it (one that ran is read by the assessment it queues) and it is waiting, running,
// stopped or failed. The encounter view's reason is worked out as if none had been asked for, so it read "wait ... before
// asking" while the request waited, and "available" once its request was used (refutation r1 re-check, ec5).
function askedSecondReview(doc) {
  const stages = Array.isArray(doc.pipeline?.stages) ? doc.pipeline.stages : [];
  const kinds = stages.map(stage => stage?.kind);
  const index = kinds.lastIndexOf('review2');
  if (index < 0 || index < kinds.lastIndexOf('assess')) return null;
  return ['queued', 'running', 'cancelled', 'failed'].includes(stages[index].state) ? stages[index] : null;
}

function sentence(text) {
  const plain = String(text || '').trim();
  return plain && !/[.!?]$/.test(plain) ? `${plain}.` : plain;
}

// The bounded second review is asked for by a reviewer, never queued by an assessment (owner decision 2026-10-27).
function secondReviewItem(doc) {
  const second = doc.second_review;
  const items = Array.isArray(second?.items) ? second.items : [];
  if (!items.length) return '';
  const what = items.join('; ');
  const asked = askedSecondReview(doc);
  if (asked) {
    const [title, said] = {
      queued: ['Second provider review requested', 'A reviewer asked for it; it is waiting to run, and nothing has been sent yet.'],
      running: ['Second provider review requested', 'A reviewer asked for it; it is running now.'],
      // Resume re-runs the latest stage only, so it runs this one only when nothing came after it
      cancelled: ['Second provider review stopped', `It was stopped before anything was sent${asked.error ? `: ${sentence(asked.error)}` : '.'}${doc.pipeline?.can_resume && doc.pipeline.stages.at(-1) === asked ? ' Resume processing runs it once.' : ''}`],
      failed: ['Second provider review did not complete', `It did not complete${asked.error ? `: ${sentence(asked.error)}` : '.'}`],
    }[asked.state];
    return checkItem(asked.state === 'failed' ? 'pending' : 'muted', 'info', title, `${said} Unresolved: ${what}.`);
  }
  if (!second.available) return checkItem('muted', 'info', 'Second provider review', `${second.reason || 'Not available now.'} Unresolved: ${what}.`);
  const body = `One more provider request, sent with only the text that documents ${items.length === 1 ? 'this item' : 'these items'}: ${what}. It is made once for this document and date; its codes fill only these items and each still needs a reviewer's decision.`;
  const button = doc.permissions?.can_review && second.can_request ? `<div class="progress-actions"><button type="button" class="button secondary" data-action="second-review">Ask the provider once more</button></div>` : '';
  return checkItem('pending', 'info', 'Second provider review available', body, button);
}

function unsupportedSection(assessment) {
  const items = Array.isArray(assessment.unsupported) ? assessment.unsupported : [];
  if (!items.length) return '';
  return `${sectionHeading('Services outside the GI profiles', items.length)}<div class="check-list-card">${items.map(item => checkItem('pending', 'info', [item.label || item.family, item.status].filter(Boolean).join(' · '), item.detail)).join('')}</div>`;
}

// The outcome of the second review made for the answer the current assessment reads (the API names it:
// second_review.run), when its response was not read or not used; '' when none was made, or its response was read and
// used. Worded from its run row, or from its own failed check when its response was refused whole (skeptic of
// refutation 7c8 reports-5: an unknown, failed or refused second review left "No CPT codes were proposed").
function secondReviewUnread(doc) {
  const id = doc?.second_review?.run;
  const run = id ? (Array.isArray(doc.provider_runs) ? doc.provider_runs : []).find(item => item?.id === id) : undefined;
  if (!run) return '';
  const items = Array.isArray(run.scope_items) && run.scope_items.length ? run.scope_items.join('; ') : 'the unresolved documented services';
  const asked = `A second review was requested for: ${items}.`;
  const none = 'This is not a finding that no codes apply.';
  if (run.state === 'succeeded') {
    if (doc.assessment?.second_run !== run.id) return `${asked} Its response has not been read by this assessment. ${none}`;
    const check = (Array.isArray(doc.assessment.encounter_checks) ? doc.assessment.encounter_checks : []).find(item => item && item.id === 'provider.second_review');
    return check && check.status === 'fail' && typeof check.detail === 'string' && check.detail ? check.detail : '';
  }
  if (run.state === 'unknown') return `${asked} It was sent, but its outcome is unknown: no response was recorded, so nothing from it was read.${run.reconciled ? ' A member reconciled it.' : ''} ${none}`;
  if (run.state === 'failed') return `${asked} It failed${run.error ? `: ${sentence(run.error)}` : '.'} Nothing from it was used. ${none}`;
  if (run.state === 'not_sent' || run.state === 'cancelled') return `${asked} Nothing was sent for it${run.error ? `: ${sentence(run.error)}` : '.'} ${none}`;
  return `${asked} It has not finished, so nothing from it was read. ${none}`;
}

function emptySelectionCopy(assessment, doc) {
  // A second review whose response was not read or not used is stated after whatever the panel says, so no wording
  // here reads as covering every response for this document (skeptic of refutation 7c8 reports-5).
  const second = secondReviewUnread(doc);
  const and = text => (second ? `${text} ${second}` : text);
  // Codes a documentation check excluded still need a reviewer decision, so the panel never says nothing was
  // proposed while they wait below (round 5, bypass:6). Only the codes still waiting are counted, as readiness
  // counts them, so a decided set is never told it needs a decision (round 6, bypass:4).
  const excluded = proposalsIn(assessment, 'excluded');
  const reinstatable = excluded.filter(proposal => proposal.reinstatable);
  const waiting = reinstatable.filter(proposal => proposal.decision_state === 'undecided' || proposal.decision_state === 'reinstated').length;
  if (waiting === 1) return and('One code that a documentation check excluded needs a reviewer\'s decision under Excluded candidates below.');
  if (waiting) return and(`${waiting} codes that a documentation check excluded need a reviewer's decision under Excluded candidates below.`);
  if (reinstatable.length) return and('Every code that a documentation check excluded has a decision; see Excluded candidates below.');
  // A provider check that failed (a response refused whole, or no usable result) says why there are no proposals;
  // "none were proposed" would misstate a response that was never read (round 7, bypass:1). So does the check of an
  // assessment that read no response at all - its provider outcome unknown, failed, or the provider not run - whatever
  // the check's status (refutation 7c8, reports-5: an unknown outcome is a 'warn').
  const provider = (Array.isArray(assessment.encounter_checks) ? assessment.encounter_checks : []).find(check => check && check.id === 'provider.status');
  const read = assessment.summary?.provider_status;
  const unread = typeof read === 'string' && read !== 'succeeded';
  const providerSays = provider && (provider.status === 'fail' || unread) && typeof provider.detail === 'string' && provider.detail ? provider.detail : '';
  // A participant's code is never a proposal in this release (refutation round 6, R6-MEANING, the session's D14): it is
  // listed as an alternative. Where every code listed is a participant's, the panel says who gave them, never
  // "independent" - a code first given in peer review never is (refutation round 7, display-2) - and never that the
  // provider proposed them, nor that it did not: a provider response refused whole, or a second review not yet read, can
  // carry the same code (refutation round 8, wording-3 and page-3). A refused or unread provider response is said first,
  // by its own check, as readiness says it first; readiness words the rest in the same words.
  const listed = [...excluded, ...proposalsIn(assessment, 'alternative')];
  const participantsOnly = 'Each code listed below was given by Astra or Fable and is offered only as an alternative.';
  if (listed.length && listed.every(proposal => proposal?.support?.origin === 'participant')) return and(providerSays ? `${providerSays} ${participantsOnly}` : `No code is selected for approval. ${participantsOnly}`);
  if (excluded.length || proposalsIn(assessment, 'alternative').length) return and('No code is selected for approval. The provider proposed only codes that were excluded or offered as alternatives; they are listed below.');
  if (providerSays) return and(providerSays);
  if (unread) return and('No provider response was read for this revision, so there are no CPT proposals.');
  // The primary response was read and selected nothing, but the second review's was not read or not used: the primary
  // check's own wording, then that review's outcome - never "none were proposed".
  if (second) return provider && typeof provider.detail === 'string' && provider.detail ? and(provider.detail) : second;
  return 'No CPT codes were proposed for this document.';
}

// Every reviewer-confirmed finding of the current revision (doc.confirmations, HARNESS.md 11.3), after its question has
// gone too: the fact and value, the passage, who located it and who confirmed it, the attestation and when. A date of
// service enters as the member's date through the encounter context. None is a decision: '' when none is served.
// Refutation round 2, truth-5: what the current assessment made of it is the API's (current_effect, the words the
// reports print as "Effect:"), never assumed - a confirmation it does not read is never said to be read.
function confirmedFindings(doc) {
  const confirmations = objects(doc.confirmations);
  if (!confirmations.length) return '';
  const exact = exactIn(doc.revision?.text);
  const items = confirmations.map(confirmation => {
    const fact = lookup(FINDING_FACTS, confirmation.fact, textValue(confirmation.fact).replace(/_/g, ' ') || 'Fact');
    const when = [formatTimestamp(confirmation.created_at), Number.isInteger(confirmation.revision_number) ? `revision ${confirmation.revision_number}` : '', confirmation.confirmed_by_kind === 'agent' ? 'agent-executed synthetic review — not clinical approval' : ''].filter(Boolean).join(' · ');
    const effect = confirmation.current_effect && typeof confirmation.current_effect === 'object' && !Array.isArray(confirmation.current_effect) ? confirmation.current_effect : {};
    const detail = textValue(effect.detail).trim();
    const effectLine = confirmation.fact === 'service_date'
      ? ['It entered as the member\'s date of service, through the encounter context.', effect.state === 'not_read' && detail ? sentence(`Effect: ${detail}`) : ''].filter(Boolean).join(' ')
      : effect.state === 'read' ? 'The assessment reads it as documented by this passage; it decides no code.'
        : effect.state === 'not_read' ? `${sentence(`Effect: ${detail || 'not read by this assessment'}`)} It decides no code.`
          : 'Whether this assessment reads it is not recorded here; the Checks tab lists each confirmation it read or did not read. It decides no code.';
    const lines = [...quotedSpans(confirmation.spans, exact), `Attestation recorded: ${textValue(confirmation.attestation) || 'none recorded'}`, effectLine];
    return checkItem('', 'shield', `${fact}: ${textValue(confirmation.value) || 'no value recorded'}`, [confirmedFrom(confirmation), when].filter(Boolean).join(' · '), lines.map(line => `<p>${escapeHtml(line)}</p>`).join(''));
  }).join('');
  return `${sectionHeading('Confirmed findings (not decisions)', confirmations.length)}<div class="check-list-card confirmed-findings">${items}</div>`;
}

function suggestionsPanel(doc, layout) {
  const assessment = doc.assessment;
  const selected = proposalsIn(assessment, 'selected');
  const inline = new Set(selected.flatMap(proposal => clarificationsFor(proposal, doc).map(item => item.id)));
  const general = openClarifications(doc).filter(item => !inline.has(item.id)).map(item => clarificationCard(item, doc));
  const cards = selected.length ? selected.map(proposal => codeCard(proposal, doc, layout)) : [`<div class="check-list-card"><p class="card-empty">${escapeHtml(emptySelectionCopy(assessment, doc))}</p></div>`];
  return `<div class="card-stack">${codingBanner(doc)}${general.join('')}${cards.join('')}</div>${confirmedFindings(doc)}${documentedServices(doc)}${unsupportedSection(assessment)}${alternativesSection(doc)}${candidateSection('Excluded candidates', proposalsIn(assessment, 'excluded'), 'Excluded from CPT-only results.', doc)}<div class="review-insight">${icon('shield')}<div><strong>The source remains the starting point</strong><p>The checks hold or exclude planned, historical, cancelled and uncertain services when they recognise the wording, and they can miss wording they do not recognise. Read the document before deciding; agreement between sources is not treated as verification.</p></div></div>`;
}

function checkItems(checks) {
  if (!Array.isArray(checks) || !checks.length) return '<p class="card-empty">No checks recorded.</p>';
  return checks.map(check => {
    const [tone, iconName] = lookup(CHECK_LOOKS, check.status, ['pending', 'info']);
    const detail = `${lookup(CHECK_LABELS, check.status, 'Unknown status')}${check.detail ? ` — ${check.detail}` : ''}`;
    return checkItem(tone, iconName, check.label || check.id || 'Check', detail, check.source ? `<small class="check-source">${escapeHtml(`Source: ${check.source}`)}</small>` : '');
  }).join('');
}

function referenceItems(sources) {
  if (!Array.isArray(sources) || !sources.length) return checkItem('pending', 'clock', 'No reference source is connected', 'Every check that needs a reference stays not verified.');
  return sources.map(source => {
    const applies = source.applies === true ? 'Applies to this service date' : source.applies === false ? 'Does not apply to this service date' : 'Applicability not established';
    const window = source.effective_start && source.effective_end ? `effective ${formatDate(source.effective_start) || source.effective_start} – ${formatDate(source.effective_end) || source.effective_end}` : '';
    const notes = [source.scope_note, source.license_note].filter(Boolean).map(note => `<small class="check-source">${escapeHtml(note)}</small>`).join('');
    return checkItem(source.applies === true ? '' : 'pending', source.applies === true ? 'circle-check' : 'clock', `${source.title || source.key}${source.release ? ` (${source.release})` : ''}`, [applies, window].filter(Boolean).join(' · '), notes);
  }).join('');
}

function checksPanel(doc) {
  const assessment = doc.assessment;
  const perCode = proposalsIn(assessment, 'selected').map(proposal => `<div class="check-list-card">${groupLabel(`${proposal.code} · ${proposal.eyebrow || proposal.family_label || ''}`)}${checkItems(proposal.checks)}</div>`).join('');
  // The encounter's checks are the assessment's: they predate a reinstatement the documented services count
  // (refutation P2FR, EUS-SECOND).
  const reinstated = reinstatedCounted(doc);
  const documentedChecks = (Array.isArray(assessment.encounter_checks) ? assessment.encounter_checks : []).some(check => String(check?.id || '').startsWith('services.'));
  const predates = reinstated.length && documentedChecks ? checkItem('muted', 'info', 'Made before the reviewer\'s reinstatement', `The documented-service checks were made when the assessment ran, before the reviewer reinstated ${reinstated.join(', ')}, and do not count ${reinstated.length === 1 ? 'it' : 'them'}; the documented services and coding completeness do.`) : '';
  return `<div class="card-stack"><div class="check-list-card">${groupLabel('Encounter')}${checkItems(assessment.encounter_checks)}${predates}</div>${perCode}<div class="check-list-card">${groupLabel('Reference sources')}${referenceItems(assessment.reference_sources)}</div></div><p class="checks-disclaimer">Checks come from the connected reference files and this service's own documentation rules. Anything they do not cover is shown as not verified, and agreement between sources is not treated as verification.</p>`;
}

function timelineEntry(title, lines, struck = false) {
  return `<div class="timeline-entry"><span class="timeline-dot"></span><div><strong>${struck ? `<s>${escapeHtml(title)}</s>` : escapeHtml(title)}</strong>${lines.filter(Boolean).map(line => `<p>${escapeHtml(line)}</p>`).join('')}</div></div>`;
}

// Corti reports credits; Astra and Fable report tokens, each exactly as its vendor reported them.
function usageText(run) {
  const credits = run.usage?.creditsConsumed;
  if (typeof credits === 'number') {
    return run.usage_basis === 'provider_reported_credits_not_usd' ? `${credits} provider-reported credits (not USD)` : `${credits} credits (basis: ${run.usage_basis || 'not recorded'})`;
  }
  const tokens = [['input_tokens', 'input'], ['output_tokens', 'output']].filter(([key]) => Number.isInteger(run.usage?.[key])).map(([key, word]) => `${run.usage[key]} ${word} tokens`);
  if (tokens.length) return `${tokens.join(', ')} (vendor-reported; basis: ${run.usage_basis || 'not recorded'})`;
  // Gemini reports usageMetadata's counts (the interpreter's runs; FINAL 6.3): prompt, output, thinking and total tokens
  const counts = [['promptTokenCount', 'prompt'], ['candidatesTokenCount', 'output'], ['thoughtsTokenCount', 'thinking'], ['totalTokenCount', 'total']]
    .filter(([key]) => Number.isInteger(run.usage?.[key])).map(([key, word]) => `${run.usage[key]} ${word} tokens`);
  return counts.length ? `${counts.join(', ')} (vendor-reported; basis: ${run.usage_basis || 'not recorded'})` : 'Usage not reported';
}

function activityPanel(doc) {
  const history = doc.decisions?.history || [];
  const runs = doc.provider_runs || [];
  const events = doc.activity || [];
  const decisions = history.map(decision => {
    const invalid = decision.invalidated ? (typeof decision.invalidated === 'string' ? decision.invalidated : decision.invalidated.reason || 'No reason recorded') : '';
    const who = [decision.reviewer, decision.reviewer_kind === 'agent' ? 'agent-executed synthetic review — not clinical approval' : 'human reviewer', formatTimestamp(decision.created_at), decision.revision_number ? `revision ${decision.revision_number}` : ''];
    return timelineEntry(`${lookup(DECISION_TITLES, decision.action, 'Decision on')} ${decision.code || ''}`.trim(), [who.filter(Boolean).join(' · '), decision.carried_from ? 'Carried forward from an earlier assessment of the same revision.' : '', decision.note ? `Note: ${decision.note}` : '', invalid ? `Invalidated: ${invalid}` : ''], Boolean(invalid));
  });
  // A second review is named on its row, with what it asked about, as both reports name it (refutation r1, report-10:
  // the primary request and the second review read as two identical rows).
  // An independent participant's run (Astra, Fable) is named as one, with the model it asked for and the one that answered.
  const runEntries = runs.map(run => timelineEntry(
    [lookup(RUN_PROVIDERS, run.provider, run.provider || 'Provider'), lookup({ live: 'live', replay: 'REPLAY — recorded response, not live output' }, run.mode, run.mode || 'mode not recorded'), NAMED_PURPOSES.has(run.purpose) ? RUN_PURPOSES[run.purpose] : '', lookup(RUN_STATES, run.state, run.state || 'state not recorded')].filter(Boolean).join(' · '),
    [[run.http_status ? `HTTP ${run.http_status}` : 'No HTTP response recorded', typeof run.latency_ms === 'number' ? `${(run.latency_ms / 1000).toFixed(1)} s` : '', usageText(run)].filter(Boolean).join(' · '),
      typeof run.requested_model === 'string' && run.requested_model ? `Model requested: ${run.requested_model}${typeof run.returned_model === 'string' && run.returned_model ? `; answered by ${run.returned_model}` : ''}.` : '',
      run.purpose === 'second_review' && Array.isArray(run.scope_items) && run.scope_items.length ? `Asked about: ${run.scope_items.join('; ')}.` : '',
      run.reused_from ? 'Reused the stored response of an identical earlier request; no new provider call was made.' : '',
      run.reconciled ? 'Unknown outcome reconciled by a member.' : '', run.error ? `Error: ${run.error}` : '', formatTimestamp(run.created_at)]));
  const eventEntries = events.map(event => timelineEntry(event.summary || event.event || 'Event', [[event.actor || 'System', formatTimestamp(event.created_at)].filter(Boolean).join(' · ')]));
  const card = (label, entries, empty) => `<div class="timeline-card">${groupLabel(label)}${entries.length ? entries.join('') : `<p class="card-empty">${empty}</p>`}</div>`;
  return `<div class="card-stack">${card('Decisions', decisions, 'No decisions recorded yet.')}${card('Provider runs', runEntries, 'No provider request has been made for this document.')}${card('Activity', eventEntries, 'No activity recorded.')}</div>`;
}

// The participant the API's harness reports under this name (corti, astra, fable), or null.
function harnessParticipant(doc, name) {
  const participants = Array.isArray(doc?.harness?.participants) ? doc.harness.participants : [];
  return participants.find(item => item && typeof item === 'object' && item.name === name) || null;
}

// The stage rows of a revision's jobs: STAGES, with the interpret stage after extract and analyze read as the derivation
// it is on the new path wherever an interpret stage exists (FINAL 6.3-6.4); exactly STAGES otherwise.
function stagesFor(stages) {
  if (!(Array.isArray(stages) ? stages : []).some(item => item?.kind === 'interpret')) return STAGES;
  return STAGES.flatMap(([kind, label]) => (kind === 'extract' ? [[kind, label], INTERPRET_STAGE] : [[kind, kind === 'analyze' ? DERIVE_STAGE_LABEL : label]]));
}

// Each row shows the LATEST job of its stage (a context change, a resume or a second review runs a stage again: the
// first one's "Done" was shown while the new one waited), and the second review's row appears once one was asked for.
// Astra's and Fable's rows appear once their stage exists or the API's harness lists them; one not configured on this
// installation says so, never "Not started". harness@2 adds each participant's peer review and the second assessment
// after the first one (phasedJobs reads which assess is which).
function progressCard(doc) {
  const stages = Array.isArray(doc.pipeline?.stages) ? doc.pipeline.stages : [];
  const listed = kind => !PARTICIPANT_STAGES.has(kind) || stages.some(item => item?.kind === kind) || Boolean(harnessParticipant(doc, kind));
  const phased = harness2(doc) || stages.some(item => PEER_KINDS.has(item?.kind)) ? phasedJobs(stages) : null;
  const chain = stagesFor(stages);
  const base = phased ? [...chain.map(([kind, label]) => [kind, kind === 'assess' ? FIRST_ASSESS_LABEL : label]), ...PEER_STAGES, SECOND_ASSESS_STAGE] : chain;
  const rows = (stages.some(item => item?.kind === 'review2') ? [...base, SECOND_REVIEW_STAGE] : base).filter(([kind]) => listed(kind));
  const items = rows.map(([kind, label]) => {
    const stage = phased && Object.hasOwn(phased, kind) ? phased[kind] : [...stages].reverse().find(item => item?.kind === kind);
    const participant = harnessParticipant(doc, kind === 'predict' ? 'corti' : PEER_KINDS.has(kind) ? kind.slice(0, -'_peer'.length) : kind);
    if (!stage && participant?.state === 'not_configured') return checkItem('muted', 'info', label, 'Not configured on this installation');
    if (!stage) return checkItem('muted', 'clock', label, 'Not started');
    const [tone, iconName] = lookup(STAGE_LOOKS, stage.state, ['pending', 'info']);
    return checkItem(tone, iconName, label, `${lookup(STAGE_STATES, stage.state, stage.state || 'Unknown')}${stage.error ? ` — ${stage.error}` : ''}`);
  }).join('');
  const stop = doc.pipeline?.can_stop && doc.permissions?.can_review ? `<div class="progress-actions"><button type="button" class="button secondary" data-action="stop">${icon('stop')}Stop</button><p>Stop cancels queued stages and prevents an unsent provider request.</p></div>` : '';
  return `<div class="check-list-card progress-card" aria-live="polite"><div class="panel-heading">${icon('clock')}<h2>Processing this document</h2><span class="small-badge">Updates automatically</span></div>${items}${stop}</div>`;
}

// One row of the Review participants card: what it reports and its short state label, then plain sentences and small
// notes. The row names what it reports (data-participant) and the state the API gave (data-state), so the browser walk
// can hold the page to the API.
// A peer-review row names its participant and the state the API served instead (data-peer, data-peer-state).
function harnessRow(key, rowState, [look, label, labelTone], title, lines, notes = [], data = '') {
  const [tone, iconName] = look;
  const status = badge(labelTone || (tone === '' ? 'green' : tone.startsWith('pending') ? 'amber' : 'gray'), label);
  const said = lines.filter(Boolean).map(line => `<p>${escapeHtml(line)}</p>`).join('');
  const small = notes.filter(Boolean).map(note => `<small class="check-source">${escapeHtml(note)}</small>`).join('');
  const named = data || `data-participant="${escapeHtml(key)}" data-state="${escapeHtml(rowState)}"`;
  return `<div class="check-item${tone ? ` ${tone}` : ''}" ${named}>${icon(iconName)}<div><span class="participant-head"><strong>${escapeHtml(title)}</strong>${status}</span>${said}${small}</div></div>`;
}

// What one participant run's own tool calls retrieved and what its answer says it used
// (harness.participants[].references or .peer_references, HARNESS.md 11.2), counted; '' when the API serves none or the
// run has neither. A run that reused a retained answer made no tool call: its references are the retained run's
// (references.reused_from), and it says so (refutation round 2, truth-13).
function referencesNote(references) {
  if (!references || typeof references !== 'object') return '';
  const retrieved = objects(references.retrieved).length;
  const used = objects(references.used);
  const cited = used.filter(item => item.retrieved !== true).length;
  if (!retrieved && !used.length) return '';
  const said = `it says it used ${used.length}${cited ? `, ${cited} of them cited, not retrieved` : ''}.`;
  if (textValue(references.reused_from)) return `This run made no tool call: the retained run it reuses retrieved ${plural(retrieved, 'reference', 'references')} with its own tool calls; ${said}`;
  return `Its own tool calls retrieved ${plural(retrieved, 'reference', 'references')}; ${said}`;
}

// A participant's row: its state as the API reports it, with the API's own sentence - after the plain one when it gives
// none, or when the state must be said plainly (not configured, not used, unknown, blocked, failed) and its sentence
// does not say so - and what it proposed, how many of its quotes the document does not contain, whether its answer was
// reused, and the model asked for and the one that answered. A reading that proposed codes the engine cannot list
// (unlisted_codes; the API's sentence counts them) is said to have proposed none that can be listed, never none at all
// (refutation round 2, truth-11) - and so is one whose count the API could not tell (unlisted_codes null: its frozen
// reading could not be read again, refutation round 5's D13), since codes may have been left unlisted.
function participantRow(participant) {
  const name = typeof participant.name === 'string' ? participant.name : '';
  const [look, label, plain, required] = lookup(PARTICIPANT_STATES, participant.state, [['pending', 'info'], 'State not recorded', 'The state of this participant was not recorded.', 'not recorded']);
  const said = typeof participant.detail === 'string' ? participant.detail.trim() : '';
  const lines = !said ? [plain] : required && !said.toLowerCase().includes(required) ? [plain, said] : [said];
  const codes = (Array.isArray(participant.codes) ? participant.codes : []).filter(code => typeof code === 'string' && code);
  const unlisted = participant.unlisted_codes === null || (Number.isInteger(participant.unlisted_codes) && participant.unlisted_codes > 0);
  const unverified = Number.isInteger(participant.unverified_quotes) && participant.unverified_quotes > 0 ? participant.unverified_quotes : 0;
  const model = textValue(participant.model);
  const returned = textValue(participant.returned_model);
  const proposed = codes.length ? `${unlisted ? 'Codes it proposed that can be listed' : 'Codes it proposed'}: ${codes.join(', ')}.`
    : unlisted ? 'It proposed no code that can be listed.' : 'It proposed no code.';
  const notes = [
    participant.state === 'done' ? proposed : '',
    unverified ? `${plural(unverified, 'quote it gave was', 'quotes it gave were')} not found in the document text, so never used as evidence.` : '',
    participant.reused === true ? 'Reused the stored answer to an identical request; nothing new was sent.' : '',
    model && returned ? `Model requested: ${model}; answered by ${returned}.` : model ? `Model: ${model}.` : '',
    referencesNote(participant.references),
  ];
  const title = lookup(PARTICIPANT_TITLES, name, [textValue(participant.label), textValue(participant.vendor)].filter(Boolean).join(' · ') || 'Participant');
  return harnessRow(name || 'participant', textValue(participant.state), [look, label], title, lines, notes);
}

// The state a participant's peer-review row shows where the API serves no peer review for it ({}), with why: not
// configured; waiting while processing reaches it; not run when its own first reading was not used (HARNESS.md 11.1);
// otherwise none recorded, with its stage's outcome where one ran.
function peerFallback(doc, participant) {
  const first = textValue(participant.state);
  if (first === 'not_configured') return ['not_configured', ''];
  if (!['done', 'waiting', 'running'].includes(first)) return ['not_run', PEER_NOT_RUN];
  if (doc.pipeline?.busy) return ['waiting', ''];
  const stages = Array.isArray(doc.pipeline?.stages) ? doc.pipeline.stages : [];
  const stage = stages.filter(item => item?.kind === `${textValue(participant.name)}_peer`).pop();
  const outcome = stage ? sentence(`Its peer-review stage: ${lookup(STAGE_STATES, stage.state, textValue(stage.state) || 'state not recorded')}${textValue(stage.error) ? ` — ${stage.error}` : ''}`) : '';
  return ['not_run', [PEER_STATES.not_run[2], outcome].filter(Boolean).join(' ')];
}

// A model participant's peer review (HARNESS.md 11.1, 12.6): its state as the API serves it (peer.state, with its
// sentence), or the page's own reading where it serves none; the codes it proposed after peer review, never
// independent - codes_added holds only those it first proposed there, and the API's sentence names any it listed again
// that its first reading proposed (refutation round 2, truth-8); its unfound quotes; and what that run's own tool calls
// retrieved and what it says it used.
function peerRow(doc, participant) {
  const name = textValue(participant.name);
  const peer = participant.peer && typeof participant.peer === 'object' && !Array.isArray(participant.peer) ? participant.peer : {};
  const served = textValue(peer.state);
  const [shown, why] = served ? [served, textValue(peer.detail).trim()] : peerFallback(doc, participant);
  const [look, label, plain, required] = lookup(PEER_STATES, shown, [['pending', 'info'], 'State not recorded', 'The state of this peer review was not recorded.', 'not recorded']);
  const lines = !why ? [plain] : required && !why.toLowerCase().includes(required) ? [plain, why] : [why];
  const codes = strings(peer.codes_added);
  const unverified = Number.isInteger(peer.unverified_quotes) && peer.unverified_quotes > 0 ? peer.unverified_quotes : 0;
  const notes = [
    codes.length ? `Codes it proposed after peer review, never independent: ${codes.join(', ')}.` : shown === 'done' ? 'It first proposed no code in peer review that can be listed.' : '',
    unverified ? `${plural(unverified, 'quote it gave was', 'quotes it gave were')} not found in the document text, so never used as evidence.` : '',
    referencesNote(participant.peer_references),
  ];
  const title = `Peer review: ${lookup(PARTICIPANT_TITLES, name, textValue(participant.label) || 'Participant')}`;
  return harnessRow(name, served, [look, label], title, lines, notes, `data-peer="${escapeHtml(name)}" data-peer-state="${escapeHtml(served)}"`);
}

function referenceRow(reference) {
  const served = reference && typeof reference === 'object' ? reference : {};
  const [look, label, plain, required] = lookup(REFERENCE_STATES, served.state, REFERENCE_STATES.not_run);
  const counted = name => (Number.isInteger(served[name]) && served[name] >= 0 ? served[name] : 0);
  // a failed retrieval, or one no CMS reference file applied to, says why in the API's own sentence (its detail), after
  // the plain one where it does not say so
  const said = served.state === 'failed' || served.state === 'not_verified' ? textValue(served.detail).trim() : '';
  const lines = served.state === 'done' ? [`${plural(counted('codes_checked'), 'code', 'codes')} checked against the CMS reference files; ${plural(counted('passages'), 'passage', 'passages')} of verbatim CMS text retrieved.`]
    : !said ? [plain] : required && !said.toLowerCase().includes(required) ? [plain, said] : [said];
  const sources = (Array.isArray(served.sources) ? served.sources : []).filter(source => source && typeof source === 'object').map(source => {
    const window = textValue(source.effective_start) && textValue(source.effective_end) ? `effective ${formatDate(source.effective_start) || source.effective_start} – ${formatDate(source.effective_end) || source.effective_end}` : '';
    return [`${textValue(source.title) || textValue(source.key) || 'CMS source'}${textValue(source.release) ? ` (${source.release})` : ''}`, window].filter(Boolean).join(' · ');
  });
  const missing = (Array.isArray(served.not_connected) ? served.not_connected : []).filter(item => typeof item === 'string' && item);
  return harnessRow('reference_validation', textValue(served.state) || 'not_run', [look, label], 'Reference validation', lines, [...sources, missing.length ? `Not connected: ${missing.join('; ')}.` : '']);
}

// Questions are asked only by CPT Studio's own readers and rules; a participant's own questions never hold the reviewed
// report (HARNESS.md 5). The row only counts (refutation round 5, the session's D11; d8-1, truth-4, parity-1, truth-5;
// HARNESS.md 12.10 as amended): how many questions are open and what each is about - the encounter (scope encounter, no
// proposal), a code (a proposal) or a documented service (scope service, no proposal) - and nothing else. It reads no
// decision, no finality and no service a code carries, so it never says what a question holds, whether its code can
// still be rejected, which service no code carries, or how a question is settled: round 4's row (d7-3) said what each
// holds by the readiness rules, and was false beside a code already rejected, a first assessment that is not final,
// and a service 45385 carries. What holds the reviewed report is readiness's to say (review.readiness's blockers,
// which exportStatusText draws as "Still needed: ..."), and this row restates none of it. Where the questions served
// do not account for the API's count, it says only the count.
// No assessment of the current revision: none at all (doc.assessment null), or doc.assessment is an earlier revision's -
// the API serves the clarification count as null while the current revision has none (serializers.harness_json;
// refutation round 6, row-1). One rule for the Clarification row and the Final status row's note (phaseNote; refutation
// round 7, parity-1).
function revisionUnassessed(doc) {
  return !doc.assessment || doc.harness?.clarification?.open === null;
}

function clarificationRow(doc) {
  const served = doc.harness?.clarification?.open;
  const open = Number.isInteger(served) && served >= 0 ? served : openClarifications(doc).length;
  const note = 'A participant\'s own questions never hold the reviewed report.';
  // No assessment of this revision: none at all (doc.assessment null), or doc.assessment is an earlier revision's - the
  // API serves the count as null while the current revision has none (after an addendum, until its revision is first
  // assessed; refutation round 6, row-1: the API served 0 there, and the row drew "None open" beside that assessment's
  // questions, which the page draws). One is coming while a stage runs; otherwise none was made (the text could not be
  // read, processing stopped, the outcome is unknown), and nothing asks a question of this revision until one is.
  // Waiting says only when the questions are known, no longer why one is asked (refutation round 5, D11): "only where
  // the documentation leaves open something that changes the coding" did not fit a member's entry that conflicts with
  // the document, or a diagnostic code asked about beside its interventions.
  const unassessed = revisionUnassessed(doc);
  if (unassessed && doc.pipeline?.busy) return harnessRow('clarification', 'waiting', [STAGE_LOOKS.queued, 'Waiting'], 'Clarification', ['Known once the proposals are checked.']);
  if (unassessed) return harnessRow('clarification', 'not_run', [['muted', 'info'], 'Not asked'], 'Clarification', ['No question was asked: the proposals were not checked for this revision.']);
  if (open > 0) {
    const asked = openClarifications(doc);
    const encounter = asked.filter(item => item.scope === 'encounter' && !item.proposal_id).length;
    const codes = asked.filter(item => item.proposal_id).length;
    const services = asked.filter(item => item.scope === 'service' && !item.proposal_id).length;
    const lines = encounter + codes + services !== open ? [`${open === 1 ? 'One question is' : `${open} questions are`} open.`] : [
      encounter === 1 ? 'One open question is about the encounter.' : encounter ? `${encounter} open questions are about the encounter.` : '',
      codes === 1 ? 'One open question is about a code.' : codes ? `${codes} open questions are each about a code.` : '',
      services === 1 ? 'One open question is about a documented service.' : services ? `${services} open questions are each about a documented service.` : '',
    ];
    return harnessRow('clarification', 'open', [['pending', 'help'], `${open} open`], 'Clarification', lines, [note]);
  }
  return harnessRow('clarification', 'none', [STAGE_LOOKS.succeeded, 'None open'], 'Clarification', ['No question is open for this revision.'], [note]);
}

// The encounter's own state, labelled as the documents list labels it (harness.final), and what approval takes.
function finalRow(doc) {
  const served = doc.harness?.final && typeof doc.harness.final === 'object' ? doc.harness.final : {};
  const stateName = textValue(served.state) || textValue(doc.state);
  const label = textValue(served.label) || textValue(doc.state_label) || 'State not recorded';
  const incomplete = reviewedIncomplete({ state: stateName, coding_state: doc.coding_state });
  const tone = incomplete ? 'amber' : lookup(STATE_TONES, stateName, 'gray');
  const look = stateName === 'processing' ? STAGE_LOOKS.running : { green: STAGE_LOOKS.succeeded, amber: ['pending', 'info'] }[tone] || ['muted', 'info'];
  const said = doc.readiness?.reviewed === true
    ? `Every selected code has a reviewer's decision.${hasAgentDecision(doc) ? ' Includes agent-executed synthetic review — not clinical approval.' : ''}`
    : 'A code is approved only by a workspace member\'s decision; agreement between participants approves nothing.';
  return harnessRow('final', stateName, [look, incomplete ? `${label} · coding incomplete` : label, tone], 'Final status', [said], [phaseNote(doc)]);
}

// Which assessment the review reads (harness.phase, HARNESS.md 12.3); '' for a payload without one, or Corti only. A
// phase-1 assessment read no peer review, whatever runs the revision holds; each peer row says why (truth-9). With no
// assessment of the current revision (revisionUnassessed) harness.phase is 1 whatever was read before, so the note says
// none was made, never "Assessed ..." (refutation round 7, parity-1: "Assessed from the frozen first readings; no peer
// review was read by this assessment." beside the Clarification row's "Not asked", in the addendum window after a stop
// and before any assessment); one is coming while a stage runs.
function phaseNote(doc) {
  if (!harness2(doc)) return '';
  if (revisionUnassessed(doc)) return doc.pipeline?.busy ? 'The peer reviews and the second assessment follow the first assessment.' : 'No assessment of this revision was made.';
  if (doc.harness.phase === 2) return 'Assessed after peer review: both phases reconciled from source evidence and rules, never by counting agreement.';
  return doc.pipeline?.busy ? 'The peer reviews and the second assessment follow the first assessment.' : 'Assessed from the frozen first readings; no peer review was read by this assessment.';
}

// The Review participants card (HARNESS.md 7) heads the review column in every state, processing included: Corti, Astra,
// Fable, reference validation, clarification and the final status, each as the API's harness reports it, and the owner's
// way to the trace. A payload served before the harness existed has none, and the page is drawn as before.
function participantsCard(doc) {
  const harness = doc?.harness;
  if (!harness || typeof harness !== 'object' || !Array.isArray(harness.participants)) return '';
  const rows = harness.participants.filter(item => item && typeof item === 'object').map(participantRow);
  // harness@2: each model participant's peer review after every first reading (HARNESS.md 11.1)
  if (harness2(doc)) rows.push(...objects(harness.participants).filter(item => item.name === 'astra' || item.name === 'fable').map(item => peerRow(doc, item)));
  rows.push(referenceRow(harness.reference_validation), clarificationRow(doc), finalRow(doc));
  const trace = OPERATOR_CONSOLE ? `<div class="progress-actions"><a class="button secondary" href="#/encounters/${escapeHtml(encodeURIComponent(doc.id))}/trace">${icon('file')}Open the trace</a><p>Operator diagnostics: every request with its endpoint, models, usage and estimated cost, each reading in full, the retrieved references and the reconciliation.</p></div>` : '';
  return `<div class="check-list-card participants-card"><div class="panel-heading">${icon('shield')}<h2>Review participants</h2><span class="small-badge">Approval stays with a reviewer</span></div>${rows.join('')}${trace}</div>`;
}

function infoCard(titleHtml, lines, actions = '') {
  return `<div class="clarification-card"><span class="clarification-icon">${icon('info')}</span><h3>${titleHtml}</h3>${lines.filter(Boolean).map(line => `<p>${escapeHtml(line)}</p>`).join('')}${actions}</div>`;
}

function reconcileCard(doc) {
  const run = (doc.provider_runs || []).filter(item => item.state === 'unknown' && !item.reconciled).pop();
  const canReview = doc.permissions?.can_review;
  // An independent participant's request is named: its unknown outcome blocks every send for the encounter too.
  // The interpreter's run too: its unknown outcome is reconciled before the document is read again (FINAL 6.9).
  const participant = PARTICIPANT_STAGES.has(run?.provider) ? PARTICIPANT_TITLES[run.provider] : run?.purpose === 'interpretation' ? INTERPRETER_TITLE : '';
  const detail = run ? `<div class="clarification-question"><strong>Unreconciled request</strong><br>${escapeHtml([participant, ['second_review', 'peer_review', 'interpretation'].includes(run.purpose) ? RUN_PURPOSES[run.purpose] : '', formatTimestamp(run.created_at), run.error].filter(Boolean).join(' · ') || 'No further detail was recorded.')}</div>` : '';
  const form = run && canReview ? `<form id="reconcileForm" data-run="${escapeHtml(run.id)}" novalidate><label class="field-label">Reconciliation note<textarea id="reconcileNote" rows="3" maxlength="2000" placeholder="What is known about this request…"></textarea></label><p class="form-error" id="reconcileError" role="alert" hidden></p><button type="submit" class="button primary">Record reconciliation ${icon('check')}</button></form>` : '';
  const viewer = run && !canReview ? '<p class="checks-disclaimer">Only owners and reviewers can record a reconciliation.</p>' : '';
  return `<div class="clarification-card"><span class="clarification-icon">${icon('help')}</span><h3>The provider outcome<br>is unknown.</h3><p>A request was sent but no response was recorded. Nothing is resent automatically: record what is known before one new attempt is allowed.</p>${detail}${form}${viewer}</div>`;
}

// The interpreter hold (FINAL 11.2), installation-wide: each standing hold with what it means and what set it, this web
// process's own interpreter mode beside it (a worker's mode is the worker's own), and its recorded release - the same act
// as `manage.py interpreter_hold --release` - with a note saying why the hold may end. Members then Resume.
function interpreterHoldCard(interpreter) {
  const standing = objects(interpreter?.standing);
  const lines = [
    'Reading documented procedures is paused on this installation: each interpret stage ends paused and sends nothing to Gemini until the hold is released.',
    ...standing.map(hold => [`Hold ${textValue(hold.id) || 'not identified'}: ${textValue(hold.means) || 'an unrecorded reason'} (${textValue(hold.reason) || 'no reason recorded'})`,
      Number.isInteger(hold.http_status) ? `HTTP ${hold.http_status}` : 'no HTTP status', textValue(hold.vendor_status),
      Number.isInteger(hold.violations) && hold.violations > 0 ? plural(hold.violations, 'quota violation', 'quota violations') : '',
      `set ${formatTimestamp(hold.set_at) || 'at a time not recorded'} by the run ${textValue(hold.run) || 'not recorded'}`].filter(Boolean).join(' · ')),
    `This web process's interpreter mode: ${textValue(interpreter?.process_mode) || 'not reported'} (the worker's mode is its own).`,
  ];
  const form = '<form id="releaseHoldForm" novalidate><label class="field-label">Release note<textarea id="releaseHoldNote" rows="3" maxlength="2000" placeholder="Why the hold may end…"></textarea></label><p class="form-error" id="releaseHoldError" role="alert" hidden></p>'
    + `<button type="submit" class="button primary">Release the hold ${icon('check')}</button></form>`;
  return `<div data-interpreter-hold>${infoCard('Reading is paused<br>on this installation.', lines, form)}</div>`;
}

// The latest stage of the revision when it is an interpret stage that FAILED (nothing runs after a failed reading), else
// null: the reading could not be completed, and the recorded retry applies (FINAL 11.3).
function failedReading(doc) {
  const stages = Array.isArray(doc?.pipeline?.stages) ? doc.pipeline.stages : [];
  const latest = stages[stages.length - 1];
  return !doc?.pipeline?.busy && latest?.kind === 'interpret' && latest.state === 'failed' ? latest : null;
}

// A reading that could not be completed (FINAL 6.3, 11.3): what its stage and its run recorded, and the recorded retry -
// one more attempt, as a stage of its own, the failed attempt released for that attempt only. An answer cut off at its
// output limit is never retried for a member (C5); an operator may override that refusal here, and the audit row records
// the override with the operator's name. A refusal is said in the server's words. The retry is an operator's act (the
// operator grant, never a workspace membership: studio.operator.retry_reading), offered while nothing runs.
function retryReadingCard(doc, stage, run) {
  const lines = [
    stage?.error ? `${INTERPRET_STAGE[1]}: ${stage.error}` : 'The reading of this document could not be completed.',
    run ? [`Interpreter run ${textValue(run.id) || 'not identified'}`, lookup(RUN_STATES, run.state, textValue(run.state) || 'state not recorded'),
      Number.isInteger(run.http_status) ? `HTTP ${run.http_status}` : '', textValue(run.error)].filter(Boolean).join(' · ') : '',
    'Nothing is sent again by itself.',
  ];
  const form = !doc.pipeline?.busy ? '<form id="retryReadingForm" novalidate><label class="check-label"><input type="checkbox" id="retryOverride"><span>Override the refusal of an answer cut off at its output limit: recorded with your name, and never offered to a member.</span></label><p class="form-error" id="retryReadingError" role="alert" hidden></p>'
    + `<button type="submit" class="button primary">Retry the reading ${icon('arrow')}</button></form>` : '';
  return `<div data-retry-reading>${infoCard('The document could<br>not be read.', lines, form)}</div>`;
}

function stateCards(doc) {
  const cards = [];
  if (doc.pipeline?.busy) cards.push(progressCard(doc));
  if (state.session?.interpreter?.held === true) cards.push(interpreterHoldCard(state.session.interpreter));
  const runs = doc.provider_runs || [];
  const stages = doc.pipeline?.stages || [];
  const reading = failedReading(doc);
  // Any unreconciled unknown outcome, the second review's included: nothing is sent again until it is reconciled.
  if (doc.state === 'provider_unknown' || runs.some(run => run.state === 'unknown' && !run.reconciled)) cards.push(reconcileCard(doc));
  if (doc.state === 'extraction_failed') {
    cards.push(infoCard('The text could not<br>be read.', ['No CPT proposals were requested because no text could be extracted; the reasons are listed above the document. Upload another copy, or paste the text instead.'], `<button type="button" class="button primary" data-action="upload">${icon('plus')}New document</button>`));
  }
  if (doc.state === 'provider_failed') {
    // The run this state reads, as the API names it (state_run): never one picked by recency - an earlier failed request
    // for another date (ec5 re-check), nor a newer one a Stop or the sweep settled before sending (ec5 skeptic).
    const failed = doc.state_run ? runs.find(run => run?.id === doc.state_run) : undefined;
    if (failed?.purpose === 'interpretation' || reading) {
      // the interpreter's run (FINAL 6.11): the reading could not be completed, and the recorded retry is offered
      cards.push(retryReadingCard(doc, reading, failed?.purpose === 'interpretation' ? failed : null));
    } else if (failed?.state === 'succeeded') {
      // A response refused whole (the state reads that run): read and not used, never a failed request nor one that
      // returned no proposals; its own failed check says why (round 7 bypass:1; skeptic of refutation 7c8 reports-5).
      const checks = Array.isArray(doc.assessment?.encounter_checks) ? doc.assessment.encounter_checks : [];
      const own = failed.purpose === 'second_review' ? ['provider.second_review'] : ['provider.status', 'provider.problems'];
      const said = own.map(id => checks.find(check => check && check.id === id)?.detail).filter(text => typeof text === 'string' && text);
      cards.push(infoCard('The provider response<br>was not used.', [...(said.length ? said : ['The response was refused whole, so there are no CPT proposals from it.']), 'Nothing was resent automatically, and any recorded usage is kept.']));
    } else {
      cards.push(infoCard('The provider request<br>failed.', [failed?.error ? `Error: ${failed.error}` : 'The provider did not return proposals.', 'Nothing was resent automatically, and any recorded usage is kept.']));
    }
  }
  if (doc.state === 'provider_not_run') {
    // the latest predict is the one that did not run: an earlier one that ran says nothing about it
    const predict = [...stages].reverse().find(stage => stage?.kind === 'predict');
    if (reading) cards.push(infoCard('The document was<br>not read.', [`${INTERPRET_STAGE[1]}: ${reading.error || 'the stage did not run for this revision.'}`]));
    else cards.push(infoCard('No proposals were<br>requested.', [predict?.error || (state.session?.provider_mode === 'disabled' ? 'Provider requests are disabled in this deployment.' : 'The provider step did not run for this revision.')]));
  } else if (reading && doc.state !== 'provider_failed') {
    cards.push(retryReadingCard(doc, reading, null));
  }
  if (doc.state === 'stopped') {
    const resume = doc.pipeline?.can_resume ? `<button type="button" class="button primary" data-action="resume">${icon('arrow')}Resume processing</button>` : '';
    // A stage the system cancelled (it expired in the queue, or a worker stopped mid-stage) is not a member's Stop:
    // say what was recorded instead of telling the member they stopped it.
    const cause = [...stages].reverse().find(stage => stage.state === 'cancelled' && stage.error);
    if (doc.pipeline?.stopped_by_member === false && cause) {
      // a reading paused on the installation (FINAL 11.2) is named by its stage too: its error is the paused message
      const label = lookup(Object.fromEntries([...STAGES, ...PEER_STAGES, INTERPRET_STAGE]), cause.kind, 'A processing stage');
      cards.push(infoCard('Processing did<br>not finish.', [`${label}: ${cause.error}`, 'Nothing was resent automatically.'], resume));
    } else {
      cards.push(infoCard('Processing was<br>stopped.', ['Queued stages were cancelled, and no unsent provider request is made unless processing is resumed.'], resume));
    }
  }
  return cards.join('');
}

// --- the operator's interpretation section (the Gemini migration; FINAL 3.1, 8.3; D22) --------------------------------

// Whether the assessment shown is a new-path one, with its interpretation section served (an earlier assessment's says it
// was read by the legacy reader, and its page is drawn as before).
function interpreted(doc) {
  return doc?.assessment?.interpretation?.engine === 'events';
}

// The review tabs of a document: Suggestions, Checks and Activity, and Interpretation for a new-path assessment.
function tabsFor(doc) {
  return interpreted(doc) ? [...TABS, INTERPRETATION_TAB] : TABS;
}

function words(value) {
  return textValue(value).replace(/_/g, ' ');
}

// One attribute of an event as the inventory stores it (the contract's 4.2 record): its value, its basis, its state and the
// reasons it is not verified, and the document's words it cites - an exact slice of the revision text.
function attributeLine(label, attribute) {
  if (!attribute || typeof attribute !== 'object') return `${label}: ${attribute === null || attribute === undefined || attribute === '' ? 'none' : words(attribute)}`;
  const value = words(attribute.value) || 'not stated';
  const how = [lookup(BASES, attribute.basis, ''), lookup(ATTRIBUTE_STATES, attribute.state, textValue(attribute.state) || 'state not recorded')].filter(Boolean).join(', ');
  const reasons = strings(attribute.reasons).map(words);
  const quoted = attribute.words && typeof attribute.words === 'object' && textValue(attribute.words.text) ? ` · “${attribute.words.text}”` : '';
  const lesion = label === 'Target' && textValue(attribute.lesion) ? ` (lesion ${attribute.lesion}${textValue(attribute.identity) ? `, identity ${words(attribute.identity)}` : ''})` : '';
  return `${label}: ${value}${lesion} — ${how}${reasons.length ? ` (${reasons.join(', ')})` : ''}${quoted}`;
}

// Each event of the inventory: its id, family, act and whether it is current, then every attribute it states.
function inventoryEvents(inventory, doc) {
  const events = objects(inventory?.events?.events);
  if (!events.length) return '<p class="harness-note">The inventory records no event.</p>';
  return events.map(event => {
    const unverified = EVENT_ATTRIBUTES.some(([key]) => event[key] && typeof event[key] === 'object' && ['unverified', 'discarded'].includes(event[key].state));
    const family = textValue(event.family) ? (doc ? familyLabel(doc, event.family) : event.family) : 'no family';
    const title = [textValue(event.id) || 'Event', family, words(event.kind?.value) || 'act not stated', `current: ${words(event.current) || 'not recorded'}`].join(' · ');
    const lines = EVENT_ATTRIBUTES.filter(([key]) => event[key] !== undefined && event[key] !== null && event[key] !== '').map(([key, label]) => attributeLine(label, event[key]));
    if (textValue(event.catalogue_kind)) lines.push(`Catalogue act: ${words(event.catalogue_kind)}${textValue(event.code_technique) ? ` · technique for coding: ${words(event.code_technique)}` : ''}`);
    return checkItem(unverified ? 'pending' : '', unverified ? 'info' : 'circle-check', title, '', lines.map(line => `<p>${escapeHtml(line)}</p>`).join(''));
  }).join('');
}

// The verification report (contract 5): per attribute how many were claimed, verified, unverified, absent, discarded and
// open; the reasons counted; the relations by type; what normalization discarded; and its problems.
function verificationReport(verification) {
  const report = verification && typeof verification === 'object' ? verification : {};
  const counts = report.counts && typeof report.counts === 'object' ? Object.entries(report.counts) : [];
  const countLines = counts.map(([name, row]) => `${words(name)}: ${['claimed', 'verified', 'unverified', 'absent', 'discarded', 'open'].map(key => `${Number.isInteger(row?.[key]) ? row[key] : 0} ${key}`).join(', ')}`);
  const tally = value => (value && typeof value === 'object' ? Object.entries(value).map(([key, count]) => `${words(key)} ${textValue(count)}`) : []);
  const listed = (title, items) => (items.length ? `${groupLabel(title)}<ul class="trace-list">${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : '');
  const discarded = objects(report.discarded).map(item => `${textValue(item.where) || 'somewhere'}: ${words(item.reason) || 'no reason recorded'}`);
  return `<div class="check-list-card">${groupLabel(`Verification report${report.refused === true ? ' · refused' : ''}`)}${countLines.length ? `<ul class="trace-list">${countLines.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : '<p class="harness-note">No attribute was counted.</p>'}${listed('Reasons', tally(report.reasons))}${listed('Relations', tally(report.relations))}${listed('Discarded', discarded)}${listed('Problems', strings(report.problems))}</div>`;
}

// The interpreter's run as the section serves it: what was asked for and what answered, its outcome, the usage Gemini
// reported and the cost estimated from the dated published rates - never the request body, the response or a key.
function interpreterRunFields(run) {
  const usage = usagePairs(run.usage && typeof run.usage === 'object' ? run.usage : {});
  const cost = textValue(run.estimated_cost);
  return traceFields([
    ['Run', shownOr(run.id)],
    ['Provider', lookup(RUN_PROVIDERS, run.provider, shownOr(run.provider))],
    ['Purpose', lookup(RUN_PURPOSES, run.purpose, shownOr(run.purpose))],
    ['State', lookup(RUN_STATES, run.state, shownOr(run.state))],
    ['Sent', run.sent === true ? 'Yes' : run.sent === false ? 'No' : 'Not recorded'],
    ['HTTP status', Number.isInteger(run.http_status) ? String(run.http_status) : 'No HTTP response recorded'],
    ['Model requested', shownOr(run.requested_model, 'None named')],
    ['Model that answered', shownOr(run.returned_model, 'None named')],
    ['Adapter version', shownOr(run.adapter_version)],
    ['Usage', usage.length ? usage.join(' · ') : 'Not reported'],
    ['Estimated cost', cost ? `$${cost} (estimated from published rates for the day sent, not reconciled to an invoice)` : run.reused_from ? 'None: a reuse makes no request' : 'Not estimated'],
    ['Request sha256', shownOr(run.request_sha256)],
    ['Response sha256', shownOr(run.response_sha256)],
    ['Reused from', shownOr(run.reused_from, 'Not reused')],
    ['Started', formatTimestamp(run.started_at) || 'Not recorded'],
    ['Finished', formatTimestamp(run.finished_at) || 'Not recorded'],
    ['Latency', typeof run.latency_ms === 'number' ? `${(run.latency_ms / 1000).toFixed(1)} s` : 'Not recorded'],
  ]);
}

// The cards of an interpretation section (the detail's assessment.interpretation, the trace's interpretation): the D22
// record and its problems, the run with the hold it set, the event inventory with its events and verification report.
// ``doc``: the encounter detail whose family labels name the events (null on the trace page: the slugs).
function interpretationCards(section, doc = null) {
  const record = section?.record && typeof section.record === 'object' ? section.record : null;
  const inventory = section?.inventory && typeof section.inventory === 'object' ? section.inventory : null;
  const run = section?.run && typeof section.run === 'object' ? section.run : null;
  const sentinel = record?.sentinel && typeof record.sentinel === 'object' ? record.sentinel : null;
  const problems = strings(section?.problems);
  const recordCard = `<div class="check-list-card">${groupLabel('The assessment\'s record')}${traceFields([
    ['Engine', shownOr(section?.engine_version)],
    ['Interpretation', [textValue(record?.interpretation_version), textValue(record?.inventory_version)].filter(Boolean).join(' · ') || 'Not recorded'],
    ['Event inventory', record?.inventory ? [textValue(record.inventory.id), textValue(record.inventory.sha256) ? `sha256 ${record.inventory.sha256}` : ''].filter(Boolean).join(' · ') : 'Not recorded'],
    ['Interpreter run', shownOr(record?.gemini_run)],
    ['Context', shownOr(record?.context)],
    ['Member date state', record && record.member_date_state !== undefined ? JSON.stringify(record.member_date_state) : 'Not recorded'],
    ['Legacy-call sentinel', sentinel ? `${Number.isInteger(sentinel.legacy_calls) ? sentinel.legacy_calls : 'an unrecorded number of'} execution(s) of the legacy reader counted · scope ${shownOr(sentinel.scope)} · ${shownOr(sentinel.tool)} · deny set ${shownOr(sentinel.deny_size)} · positive control ${shownOr(sentinel.positive_control)}` : 'Not recorded'],
  ])}${problems.length ? `${groupLabel('Record problems')}<ul class="trace-list">${problems.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : '<p class="harness-note">The record has no problem.</p>'}</div>`;
  const hold = section?.hold && typeof section.hold === 'object' ? section.hold : null;
  const holdLine = hold ? `<p class="harness-note">${escapeHtml(`This run set the interpreter hold ${textValue(hold.id)}: ${textValue(hold.means) || textValue(hold.reason)} (${textValue(hold.reason)}); ${hold.released_at ? `released ${formatTimestamp(hold.released_at)} by ${textValue(hold.released_by) || 'an operator'}` : 'standing'}.`)}</p>` : '';
  const runCard = `<div class="check-list-card">${groupLabel(`${INTERPRETER_TITLE} · ${run ? lookup(RUN_STATES, run.state, shownOr(run.state)) : 'no run'}`)}${run ? interpreterRunFields(run) : '<p class="harness-note">No interpreter run is recorded for this inventory.</p>'}${holdLine}</div>`;
  const counts = inventory?.counts && typeof inventory.counts === 'object' ? inventory.counts : {};
  const inventoryCard = `<div class="check-list-card">${groupLabel(`Event inventory · ${inventory ? shownOr(inventory.state) : 'none'}`)}${inventory ? traceFields([
    ['Inventory', shownOr(inventory.id)],
    ['Versions', [textValue(inventory.interpretation_version), textValue(inventory.inventory_version)].filter(Boolean).join(' · ') || 'Not recorded'],
    ['Inventory sha256', shownOr(inventory.sha256)],
    ['Text sha256', shownOr(inventory.text_sha256)],
    ['Request sha256', shownOr(inventory.request_sha256)],
    ['Response sha256', shownOr(inventory.response_sha256)],
    ['Recorded', formatTimestamp(inventory.created_at) || 'Not recorded'],
    ['Contents', ['passages', 'lesions', 'events', 'relations'].map(part => `${Number.isInteger(counts[part]) ? counts[part] : 0} ${part}`).join(' · ')],
  ]) : '<p class="harness-note">The assessment names no event inventory.</p>'}</div>`;
  const relations = objects(inventory?.events?.relations).map(item => [words(item.type) || 'relation', textValue(item.event), words(item.attribute), words(item.reason), item.claimed_by_model === true ? 'claimed by the model' : ''].filter(Boolean).join(' · '));
  const questions = objects(inventory?.open_questions).map(item => [`about ${words(item.about) || 'not recorded'}`, strings(item.events).length ? `events ${strings(item.events).join(', ')}` : '', strings(item.lesions).length ? `lesions ${strings(item.lesions).join(', ')}` : ''].filter(Boolean).join(' · '));
  const listed = (title, items) => (items.length ? `<div class="check-list-card">${groupLabel(title)}<ul class="trace-list">${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul></div>` : '');
  const eventsCard = inventory ? `<div class="check-list-card">${groupLabel(`Events · ${plural(objects(inventory.events?.events).length, 'event', 'events')}`)}${inventoryEvents(inventory, doc)}</div>` : '';
  return [recordCard, runCard, inventoryCard, eventsCard, listed('Relations', relations), listed('Open questions', questions), inventory ? verificationReport(inventory.verification) : ''].join('');
}

// The Interpretation tab of a new-path assessment: the routing the codes were checked with - a stand-in derived from the
// event inventory, never a reading (FINAL 4.3) - and the section's cards.
function interpretationPanel(doc) {
  const section = doc?.assessment?.interpretation || {};
  const routing = doc?.routing && typeof doc.routing === 'object' ? doc.routing : null;
  const families = objects(routing?.families).map(family => `${familyLabel(doc, family.family)}: ${words(family.status) || 'no status'}`);
  const stand = routing?.derived === true
    ? `Routing: a stand-in derived from ${textValue(routing.derived_from) || 'the event inventory'} ${textValue(routing.inventory)}${textValue(routing.inventory_sha256) ? ` (sha256 ${routing.inventory_sha256})` : ''}, read as no reading: ${families.join('; ') || 'no family'}.`
    : routing ? `Routing: ${textValue(routing.version) || 'a reading'} (not derived from the event inventory).` : 'No routing is recorded for this assessment.';
  return `<div class="card-stack"><p class="checks-disclaimer">${escapeHtml('Gemini read the documented procedures into this event inventory; CPT Studio checked each attribute against the words it cites, and decided every code from the inventory. Interpretation and agreement are never approval.')}</p><div class="check-list-card">${groupLabel('Routing')}<p class="harness-note">${escapeHtml(stand)}</p></div>${interpretationCards(section, doc)}</div>`;
}

function tabContent(doc, tab, layout) {
  if (tab === 'interpretation' && interpreted(doc)) return interpretationPanel(doc);
  if (tab === 'checks') return checksPanel(doc);
  if (tab === 'timeline') return activityPanel(doc);
  return suggestionsPanel(doc, layout);
}

function reviewView(doc, layout, tab, entrance) {
  const selected = proposalsIn(doc.assessment, 'selected');
  const tabs = doc.assessment ? `<div class="result-tabs" role="tablist" aria-label="Review details">${tabsFor(doc).map(([id, label]) => `<button type="button" role="tab" id="tab-${id}" data-tab="${id}" aria-controls="resultContent" aria-selected="${tab === id}" tabindex="${tab === id ? 0 : -1}">${label}${id === 'codes' ? ` <span class="tab-count">${selected.length}</span>` : ''}</button>`).join('')}</div><div id="resultContent" role="tabpanel" tabindex="0" aria-labelledby="tab-${tab}">${tabContent(doc, tab, layout)}</div>` : '';
  const exportButton = doc.assessment ? `<button type="button" class="button primary" data-action="export">${icon('download')}Export</button>` : '';
  return `<section${entrance ? ' class="view-entrance"' : ''}><a class="back-link" href="#documents">${icon('arrow')}All documents</a><div class="heading-row review-heading"><div><span class="eyebrow">CPT REVIEW · SYNTHETIC</span><h1>${escapeHtml(doc.title || 'Untitled document')}</h1><div class="review-meta">${reviewMeta(doc)}</div></div><div class="heading-actions"><button type="button" class="button secondary" data-action="upload">${icon('plus')}New document</button>${exportButton}</div></div><div class="review-layout">${sourcePanel(doc, layout)}<section class="review-column" aria-label="Coding review"><div class="results-topline"><h2>Coding review</h2><span class="small-badge">CPT only</span></div>${participantsCard(doc)}${stateCards(doc)}${tabs}</section></div><div class="sample-strip"><span>SYNTHETIC DEMONSTRATION · Not clinical approval, coding advice or billing.</span><a href="#how-it-works">About the workflow ${icon('arrow')}</a></div></section>`;
}

function exportOption(kind, fmt, title, detail) {
  return `<button type="button" class="export-option" data-export-kind="${kind}" data-export-fmt="${fmt}"><span class="export-format">${fmt.toUpperCase()}</span><span><strong>${title}</strong><small>${detail}</small></span>${icon('download')}</button>`;
}

function exportOptions(readiness) {
  const draft = readiness.draft === true ? `<div class="export-group">${groupLabel('Draft — not reviewed')}${exportOption('draft', 'txt', 'Coding report (TXT)', 'Codes, evidence, checks and open questions')}${exportOption('draft', 'csv', 'Structured CSV', 'One row per code with its review state')}</div>` : '';
  const reviewed = readiness.reviewed === true ? `<div class="export-group">${groupLabel('Reviewed')}${exportOption('reviewed', 'txt', 'Coding report (TXT)', 'Approved selections, rejections and reviewers')}${exportOption('reviewed', 'csv', 'Structured CSV', 'One row per item, with decisions')}</div>` : '';
  return draft + reviewed;
}

// --- the owner's trace (HARNESS.md 7) --------------------------------------------------------------------------------

function objects(value) {
  return Array.isArray(value) ? value.filter(item => item && typeof item === 'object') : [];
}

function strings(value) {
  return Array.isArray(value) ? value.filter(item => typeof item === 'string' && item) : [];
}

function shownOr(value, fallback = 'None recorded') {
  return textValue(value) || fallback;
}

// A vendor's usage object exactly as it reported it, flattened to "key value" pairs ("input_tokens_details.cached_tokens 0").
function usagePairs(value, prefix = '', depth = 0) {
  if (value === null || typeof value !== 'object') return prefix ? [`${prefix} ${textValue(value) || 'not reported'}`] : [];
  if (depth > 4) return [`${prefix} …`];
  return Object.keys(value).flatMap(key => usagePairs(value[key], prefix ? `${prefix}.${key}` : key, depth + 1));
}

function traceFields(pairs) {
  return `<dl class="trace-fields">${pairs.map(([name, value]) => `<dt>${escapeHtml(name)}</dt><dd>${escapeHtml(value)}</dd>`).join('')}</dl>`;
}

// A quote a participant gave: one it wrote that reads like a CPT descriptor is withheld (DESCRIPTOR_LIKE).
function quoteOf(text) {
  return DESCRIPTOR_LIKE.test(text) ? '(a quote withheld: it reads like a CPT descriptor)' : `“${text}”`;
}

// The quotes a participant gave as evidence: one located in the document is the document's own text; one that is not
// is listed as unverified, and never used as evidence (HARNESS.md 4, I7).
function traceQuotes(evidence) {
  const items = (Array.isArray(evidence) ? evidence : []).map(item => {
    if (typeof item === 'string') return item.trim() ? quoteOf(item.trim()) : '';
    if (!item || typeof item !== 'object') return '';
    const quote = textValue(item.quote).trim();
    const found = Array.isArray(item.spans) ? item.spans.length : 0;
    if (found) return `“${quote}” — found in the document (${plural(found, 'place', 'places')})`;
    return `${quoteOf(quote)} — unverified${textValue(item.reason) ? ` (${item.reason})` : ''}; never used as evidence`;
  }).filter(Boolean);
  return items.length ? `<ul class="trace-quotes">${items.map(text => `<li>${escapeHtml(text)}</li>`).join('')}</ul>` : '';
}

// A participant's normalized reading in full (HARNESS.md 4): refused whole or read, its problems, the date and services it
// read, the codes it listed (each quote found in the document or unverified) and those it considered and did not, its
// questions and the places it says the extraction misreads. Its free text is a model's, so anything in it that reads
// like a CPT descriptor is withheld. Its codes' heading is neutral (refutation round 6, account-1: "Codes proposed"
// headed a code whose only quote is unverified, which the same trace says that reading did not propose).
function traceReading(reading) {
  if (!reading || typeof reading !== 'object') return '<div class="trace-reading"><p class="harness-note">No participant reading is recorded for this request.</p></div>';
  const ids = value => strings(value).join(', ');
  const date = reading.date_of_service && typeof reading.date_of_service === 'object' ? textValue(reading.date_of_service.value) : textValue(reading.date_of_service);
  const fields = traceFields([
    ['Reading', reading.refused === true ? 'Refused whole: none of it was read or used' : 'Read'],
    ['Unverified quotes', `${Number.isInteger(reading.unverified_quotes) ? reading.unverified_quotes : 0} (never used as evidence)`],
    ['Date of service as read', date || 'None read'],
  ]);
  const problems = strings(reading.problems).map(problem => `<li>${escapeHtml(problem)}</li>`);
  const services = objects(reading.services).map(service => {
    const head = [textValue(service.id), textValue(service.family).replace(/_/g, ' '), textValue(service.status).replace(/_/g, ' ')].filter(Boolean).join(' · ');
    const lines = [['Description', service.description], ['Anatomy', service.anatomy], ['Extent', service.extent], ['Technique', service.technique], ['Provider role', service.provider_role]]
      .map(([name, value]) => (participantText(value) ? `${name}: ${participantText(value)}` : ''));
    const lesions = objects(service.lesions).map(lesion => `Lesion: ${['site', 'size', 'morphology', 'action', 'specimen'].map(key => (participantText(lesion[key]) ? `${key} ${participantText(lesion[key])}` : '')).filter(Boolean).join(', ') || 'nothing recorded'}`);
    return `<li><b>${escapeHtml(head || 'Service')}</b>${[...lines, ...lesions].filter(Boolean).map(line => `<br>${escapeHtml(line)}`).join('')}${traceQuotes(service.evidence)}</li>`;
  });
  const codes = objects(reading.codes).map(code => traceCode(code));
  const notCoded = objects(reading.not_coded).map(item => `<li><b>${escapeHtml([textValue(item.code) || 'No code named', lookup(NOT_CODED_WORDS, item.reason, textValue(item.reason) || 'reason not recorded'), ids(item.service_ids) ? `services ${ids(item.service_ids)}` : ''].filter(Boolean).join(' · '))}</b>${traceQuotes(item.evidence)}</li>`);
  const questions = objects(reading.questions).map(item => `<li><b>${escapeHtml(participantText(item.question) || 'Question not recorded')}</b>${participantText(item.why) ? `<br>${escapeHtml(`Why: ${participantText(item.why)}`)}` : ''}${ids(item.service_ids) ? `<br>${escapeHtml(`Services: ${ids(item.service_ids)}`)}` : ''}${traceQuotes(item.evidence)}</li>`);
  const issues = objects(reading.extraction_issues).map(item => `<li>${escapeHtml(`Page ${textValue(item.page) || 'not given'}: ${participantText(item.issue) || 'no issue recorded'}`)}</li>`);
  const group = (title, items, empty) => `${groupLabel(`${title} · ${items.length}`)}${items.length ? `<ul class="trace-list">${items.join('')}</ul>` : `<p class="harness-note">${escapeHtml(empty)}</p>`}`;
  // harness@2: the references it says it used, each checked against this run's own tool calls (HARNESS.md 11.2)
  const used = Array.isArray(reading.references_used) ? group('References it says it used', traceReferencesUsed(reading.references_used), 'None cited.') : '';
  return `<div class="trace-reading">${fields}${problems.length ? `${groupLabel('Problems')}<ul class="trace-list">${problems.join('')}</ul>` : ''}${group('Services', services, 'No service listed.')}${group('Codes it listed', codes, 'No code listed.')}${group('Considered and not coded', notCoded, 'Nothing listed.')}${group('Questions (notes; they never hold the report)', questions, 'No question.')}${group('Extraction issues', issues, 'None reported.')}${used}</div>`;
}

// One code a participant proposed, with what it stated and the quotes it gave; ``after``: said of a code first proposed
// in peer review (HARNESS.md 11.1).
function traceCode(code, after = '') {
  const ids = value => strings(value).join(', ');
  const head = [`${textValue(code.code) || 'No code'}${ids(code.modifiers) ? ` (modifiers ${ids(code.modifiers)})` : ''}`, Number.isInteger(code.units) ? `units ${code.units}` : '', textValue(code.confidence) ? `confidence ${code.confidence}` : '', ids(code.service_ids) ? `services ${ids(code.service_ids)}` : '', after].filter(Boolean).join(' · ');
  const basis = participantText(code.basis);
  return `<li><b>${escapeHtml(head)}</b>${basis ? `<br>${escapeHtml(`Basis: ${basis}`)}` : ''}${traceQuotes(code.evidence)}</li>`;
}

// The references a participant's answer says it used (references_used), each with CPT Studio's check against that run's
// own tool calls: one it cited and never retrieved is marked so, never shown as retrieved (HARNESS.md 11.2). A run that
// reused a retained answer was checked against the retained run's tool calls (each item's reused_from), and says so
// (refutation round 2, truth-13).
function traceReferencesUsed(items) {
  return objects(items).map(item => {
    const use = participantText(item.use);
    const checked = textValue(item.reused_from)
      ? (item.retrieved === true ? `retrieved by the tool calls of the retained run this run reuses (${item.reused_from})` : `cited, not retrieved by the retained run this run reuses (${item.reused_from})`)
      : (item.retrieved === true ? 'retrieved by its own tool calls in this run' : 'cited, not retrieved');
    return `<li><b>${escapeHtml(`${participantText(shownReference(item)) || 'Reference not named'} — ${checked}`)}</b>${use ? `<br>${escapeHtml(`Its use: ${use}`)}` : ''}</li>`;
  });
}

// A peer review in full (HARNESS.md 11.1; the PeerReview the trace serves as ``review``): refused whole or read, the
// frozen inputs it was shown with their sha256, its answers to CPT Studio's open questions (by question id), its
// positions on codes, its additional codes (each worded by the phase served with it), the references it says it used
// and its problems. Its free text is a model's, so anything that reads like a CPT descriptor is withheld. The
// additional codes' heading is neutral (refutation round 6, account-1: "Codes proposed after peer review" headed a code
// listed in peer review, its only quote unverified).
function traceReview(review) {
  if (!review || typeof review !== 'object') return '<div class="trace-reading"><p class="harness-note">No peer review is recorded for this request.</p></div>';
  const fields = traceFields([
    ['Peer review', review.refused === true ? 'Refused whole: none of it was read or used' : 'Read'],
    ['Unverified quotes', `${Number.isInteger(review.unverified_quotes) ? review.unverified_quotes : 0} (never used as evidence)`],
    ['Review version', shownOr(review.review_version)],
  ]);
  const frozen = (Array.isArray(review.frozen_inputs) ? review.frozen_inputs : []).filter(Array.isArray).map(([name, digest]) => [textValue(name) || 'input', textValue(digest) || 'not recorded']);
  const problems = strings(review.problems).map(problem => `<li>${escapeHtml(problem)}</li>`);
  const answers = objects(review.answers).map(answer => `<li><b>${escapeHtml(`Question ${textValue(answer.question_id) || 'not named'}`)}</b><br>${escapeHtml(answer.settled === true ? `Answer: ${participantText(answer.value) || 'no value given'}` : 'Its answer is read as not settling it.')}${traceQuotes(answer.evidence)}</li>`);
  const positions = objects(review.positions).map(item => `<li><b>${escapeHtml(`${textValue(item.code) || 'No code'} · ${lookup(PEER_POSITIONS, item.position, textValue(item.position) || 'position not recorded')}`)}</b>${participantText(item.reason) ? `<br>${escapeHtml(`Why: ${participantText(item.reason)}`)}` : ''}${traceQuotes(item.evidence)}</li>`);
  // each additional code by the phase its participant first proposed it in, where the trace serves it (truth-8): a code
  // its first reading proposed is repeated, never "never independent"; one served without a phase reads as before; null,
  // a review the current assessment did not read, says so and never "listed in peer review" (refutation round 6,
  // account-5: '' was served for such a review, and its code read "listed" beside a quote found in the document)
  const addedWords = code => (code.phase === null ? 'not read by the current assessment'
    : !Object.hasOwn(code, 'phase') || code.phase === 'peer_review' ? 'proposed after peer review, never independent'
      : code.phase === 'independent' ? 'repeated in peer review; first proposed in its independent reading' : 'listed in peer review');
  const added = objects(review.additional_codes).map(code => traceCode(code, addedWords(code)));
  const group = (title, items, empty) => `${groupLabel(`${title} · ${items.length}`)}${items.length ? `<ul class="trace-list">${items.join('')}</ul>` : `<p class="harness-note">${escapeHtml(empty)}</p>`}`;
  return `<div class="trace-reading">${fields}${groupLabel('Frozen inputs it was shown')}${frozen.length ? traceFields(frozen) : '<p class="harness-note">None recorded.</p>'}${problems.length ? `${groupLabel('Problems')}<ul class="trace-list">${problems.join('')}</ul>` : ''}${group('Answers to the open questions', answers, 'No answer.')}${group('Positions on codes', positions, 'No position.')}${group('Additional codes', added, 'No additional code.')}${group('References it says it used', traceReferencesUsed(review.references_used), 'None cited.')}</div>`;
}

// Each HTTP exchange of a participant run's tool loop (HARNESS.md 11.2) with the tool calls CPT Studio executed for it:
// the tool and its arguments - a participant's own text, shown only in the tools' own shapes (shownArguments) - the
// refs returned and the result's sha256. '' for a run served without exchanges (before harness@2) and for one with none
// (Corti's).
function traceExchanges(run) {
  const exchanges = objects(run.exchanges);
  if (!exchanges.length) return '';
  const items = exchanges.map(exchange => {
    const usage = usagePairs(exchange.usage && typeof exchange.usage === 'object' ? exchange.usage : {});
    const fields = traceFields([
      ['Turn', shownOr(exchange.turn)],
      ['State', lookup(RUN_STATES, exchange.state, shownOr(exchange.state))],
      ['HTTP status', Number.isInteger(exchange.http_status) ? String(exchange.http_status) : 'No HTTP response recorded'],
      ['Latency', typeof exchange.latency_ms === 'number' ? `${(exchange.latency_ms / 1000).toFixed(1)} s` : 'Not recorded'],
      ['Usage', usage.length ? usage.join(' · ') : 'Not reported'],
      ['Request sha256', shownOr(exchange.request_sha256)],
      ['Response sha256', shownOr(exchange.response_sha256)],
      ['Vendor request id', shownOr(exchange.provider_request_id)],
      ['Response id', shownOr(exchange.response_id)],
      ['Error', shownOr(exchange.error, 'None')],
    ]);
    const calls = objects(exchange.tool_calls).map(call => {
      const written = JSON.stringify(shownArguments(call.arguments) ?? null);
      const where = [textValue(call.result_sha256) ? `result sha256 ${call.result_sha256}` : 'no result sha256 recorded', formatTimestamp(call.executed_at) ? `executed ${formatTimestamp(call.executed_at)}` : ''].filter(Boolean).join(' · ');
      // the tool as the participant named it: a model can name one CPT Studio does not have, named only by its length
      return `<li><b>${escapeHtml(`${participantText(inShape(textValue(call.tool), TOOL_NAMES)) || 'Tool not named'}${textValue(call.call_id) ? ` (${call.call_id})` : ''}`)}</b><br>${escapeHtml(`Arguments: ${DESCRIPTOR_LIKE.test(written) ? DESCRIPTOR_WITHHELD : written}`)}<br>${escapeHtml(`Refs returned: ${strings(call.refs).join(', ') || 'none'}`)}<small class="check-source">${escapeHtml(where)}</small></li>`;
    });
    return `<div class="trace-exchange">${fields}${calls.length ? `<ul class="trace-list">${calls.join('')}</ul>` : '<p class="harness-note">No tool call in this exchange.</p>'}</div>`;
  });
  return `<div class="trace-reading">${groupLabel(`Exchanges · ${exchanges.length}`)}${items.join('')}</div>`;
}

// Each assessment of the revision (HARNESS.md 12.3), oldest first: its phase, whether it is its chain's final one and
// the current one, and the sha256 of every frozen phase-1 output it recorded.
function traceAssessments(entries) {
  const list = objects(entries);
  if (!list.length) return '<div class="check-list-card"><p class="harness-note">No assessment is recorded for this revision.</p></div>';
  return list.map(entry => {
    const title = [lookup(ASSESSMENT_PHASES, String(entry.phase), 'Phase not recorded'), entry.final === true ? 'final' : 'not final', entry.current === true ? 'current' : ''].filter(Boolean).join(' · ');
    const fields = traceFields([['Assessment', shownOr(entry.id)], ['Created', formatTimestamp(entry.created_at) || 'Not recorded']]);
    const frozen = (Array.isArray(entry.frozen) ? entry.frozen : []).filter(Array.isArray).map(([name, digest]) => [textValue(name) || 'input', textValue(digest) || 'not recorded']);
    return `<div class="check-list-card">${groupLabel(title)}${fields}${groupLabel('Frozen phase-1 outputs (sha256)')}${frozen.length ? traceFields(frozen) : '<p class="harness-note">None recorded: no model participant\'s first reading was frozen for it.</p>'}</div>`;
  }).join('');
}

// What an exchange of a tool loop that reported no usage came to (its state), in the reports' words.
const EXCHANGE_OUTCOMES = { succeeded: 'answered', failed: 'failed', unknown: 'outcome unknown' };

// Why a run has no estimate when the exchanges of its tool loop that may have been billed - every one not recorded not
// sent - reported no usage (review.unpriced_exchanges; refutation round 2, truth-12); '' otherwise.
function unpricedNote(run) {
  const exchanges = objects(run.exchanges);
  if (exchanges.length < 2) return '';
  const named = exchanges.filter(exchange => exchange.state !== 'not_sent' && !(exchange.usage && typeof exchange.usage === 'object' && Object.keys(exchange.usage).length))
    .map(exchange => `${shownOr(exchange.turn)} (${lookup(EXCHANGE_OUTCOMES, exchange.state, textValue(exchange.state) || 'state not recorded')})`);
  if (!named.length) return '';
  const which = named.length === 1 ? `exchange ${named[0]}` : `exchanges ${named.slice(0, -1).join(', ')} and ${named[named.length - 1]}`;
  return `Not estimated: ${which} reported no usage and may have been billed, so the cost of this run cannot be estimated from published rates`;
}

// One request of one participant, with every field its run records (HARNESS.md 6), then the reading made of it.
function traceRun(run) {
  const usage = usagePairs(run.usage && typeof run.usage === 'object' ? run.usage : {});
  const cost = textValue(run.estimated_cost_usd);
  const fields = [
    ['Run', shownOr(run.id)],
    ['State', lookup(RUN_STATES, run.state, shownOr(run.state))],
    ['Purpose', lookup(RUN_PURPOSES, run.purpose, shownOr(run.purpose))],
    ['Adapter version', shownOr(run.adapter_version)],
    ['Endpoint', shownOr(run.endpoint)],
    ['Model requested', shownOr(run.requested_model, 'None named')],
    ['Model that answered', shownOr(run.returned_model, 'None named')],
    ['Vendor request id', shownOr(run.request_id)],
    ['Response id', shownOr(run.response_id)],
    ['HTTP status', Number.isInteger(run.http_status) ? String(run.http_status) : 'No HTTP response recorded'],
    ['Latency', typeof run.latency_ms === 'number' ? `${(run.latency_ms / 1000).toFixed(1)} s` : 'Not recorded'],
    ['Usage', usage.length ? usage.join(' · ') : 'Not reported'],
    ['Usage basis', shownOr(run.usage_basis)],
    ['Estimated cost', cost ? `$${cost} (estimated from published rates, not reconciled to an invoice)` : unpricedNote(run) || 'Not estimated'],
    ['Request sha256', shownOr(run.request_sha256)],
    ['Response sha256', shownOr(run.response_sha256)],
    ['Response bytes', Number.isInteger(run.response_bytes) ? String(run.response_bytes) : 'None recorded'],
    ['Created', formatTimestamp(run.created_at) || 'Not recorded'],
    ['Finished', formatTimestamp(run.finished_at) || 'Not recorded'],
    ['Reused from', shownOr(run.reused_from, 'Not reused')],
    ['Error', shownOr(run.error, 'None')],
  ];
  // harness@2's run identity and who asked (HARNESS.md 6), where the trace serves them
  if ('run_identity' in run) {
    fields.splice(1, 0, ['Mode', lookup({ live: 'live', replay: 'REPLAY — recorded response, not live output' }, run.mode, shownOr(run.mode))], ['Run identity (client request id)', shownOr(run.run_identity)]);
    fields.push(['Sent', run.sent === true ? 'Yes' : run.sent === false ? 'No' : 'Not recorded'], ['Requested by', shownOr(run.requested_by)], ['Authorization reference', shownOr(run.authorization_ref)], ['Reconciled', run.reconciled === true ? 'Yes, by a member' : 'No']);
  }
  const title = [lookup(RUN_PURPOSES, run.purpose, ''), lookup(RUN_STATES, run.state, shownOr(run.state, 'State not recorded'))].filter(Boolean).join(' · ');
  const answer = run.purpose === 'peer_review' ? traceReview(run.review) : traceReading(run.reading);
  return `<div class="check-list-card trace-run">${groupLabel(title)}${traceFields(fields)}${traceExchanges(run)}${answer}</div>`;
}

// The retrieval traces (Assessment.retrieval, HARNESS.md 5): per code, each fact looked up and each CMS passage retrieved,
// with its source, release, effective dates and sha256, then the lookups made and the notes recorded. A retrieval that
// failed is recorded as one entry marked failed, with no code (refutation round 1, parity-1): it is shown as failed, with
// its note, never as a code with nothing found.
function retrievalTraces(entries) {
  const list = objects(entries);
  if (!list.length) return '<div class="check-list-card"><p class="harness-note">No retrieval trace is recorded for this assessment.</p></div>';
  const known = new Set(['source_key', 'release', 'effective', 'sha256', 'field', 'value']);
  return list.map(entry => {
    if (entry.failed === true) {
      const notes = strings(entry.notes);
      return `<div class="check-list-card">${groupLabel('Reference validation failed')}${(notes.length ? notes : [REFERENCE_STATES.failed[2]]).map(note => `<p class="harness-note">${escapeHtml(note)}</p>`).join('')}</div>`;
    }
    const facts = objects(entry.facts).map(fact => {
      const effective = Array.isArray(fact.effective) ? fact.effective.map(value => formatDate(value) || textValue(value)).filter(Boolean).join(' – ') : '';
      const extra = Object.keys(fact).filter(key => !known.has(key)).map(key => `${key} ${textValue(fact[key]) || (fact[key] == null ? 'none' : JSON.stringify(fact[key]))}`);
      const where = [textValue(fact.source_key), textValue(fact.release), effective ? `effective ${effective}` : '', textValue(fact.sha256) ? `sha256 ${fact.sha256}` : '', ...extra].filter(Boolean).join(' · ');
      return `<li><b>${escapeHtml(`${textValue(fact.field) || 'Fact'}: ${textValue(fact.value) || 'not recorded'}`)}</b><small class="check-source">${escapeHtml(where)}</small></li>`;
    });
    const passages = objects(entry.passages).map(passage => {
      const page = textValue(passage.page);
      const title = [textValue(passage.section) || 'CMS passage', page ? `page ${page}` : '', [textValue(passage.source_key), textValue(passage.release)].filter(Boolean).join(' ')].filter(Boolean).join(' · ');
      const where = [textValue(passage.passage_key) ? `passage ${passage.passage_key}` : '', textValue(passage.topic) ? `topic ${passage.topic}${textValue(passage.topic_value) ? ` = ${passage.topic_value}` : ''}` : '', textValue(passage.sha256) ? `sha256 ${passage.sha256}` : ''].filter(Boolean).join(' · ');
      return `<details class="reference-passage"><summary>${escapeHtml(title)}</summary><p>${escapeHtml(textValue(passage.text))}</p><small class="check-source">${escapeHtml(where)}</small></details>`;
    });
    const listed = (title, items) => (items.length ? `${groupLabel(title)}<ul class="trace-list">${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : '');
    const date = textValue(entry.service_date);
    return `<div class="check-list-card">${groupLabel(`${textValue(entry.code) || 'Code'} · service date ${formatDate(date) || date || 'not established'}`)}${facts.length ? `<ul class="trace-list">${facts.join('')}</ul>` : '<p class="harness-note">No fact was found for this code.</p>'}${passages.join('')}${listed('Lookups', strings(entry.lookups))}${listed('Notes', strings(entry.notes))}</div>`;
  }).join('');
}

// The reconciliation table (HARNESS.md 5): per code, who proposed it, each participant's position, the CMS reference
// checks and whether a member approved it - four statements, never merged into one (I4).
function traceReconciliation(rows) {
  const list = objects(rows);
  if (!list.length) return '<div class="check-list-card"><p class="harness-note">No reconciliation is recorded for this assessment.</p></div>';
  return `<div class="check-list-card">${list.map(row => {
    const proposers = strings(row.proposed_by).map(name => lookup(PARTICIPANT_LABELS, name, name));
    // a participant that only listed the code is named apart, never as a proposer (refutation round 5, D12)
    const listed = listedText(row.listed_by, proposers.length > 0);
    const proposed = proposers.length ? [proposers.join(', '), listed].filter(Boolean).join('; ') : listed ? `no participant; ${listed}` : 'not recorded';
    const positions = row.positions && typeof row.positions === 'object' && !Array.isArray(row.positions) ? Object.keys(row.positions).map(name => {
      const value = row.positions[name];
      return value && typeof value === 'object' ? positionText(name, value) : `${lookup(PARTICIPANT_LABELS, name, name)} ${lookup(POSITION_WORDS, value, 'took a position that was not recorded')}`;
    }) : [];
    const check = row.reference_check;
    const reference = check && typeof check === 'object' ? referenceCheckText(check) : referenceCheckText({ state: check });
    const approved = row.approved === true ? 'approved by a workspace member' : row.approved === false ? 'not approved' : 'not recorded';
    const lines = [`Proposed by: ${proposed}`, ...(positions.length ? positions : ['Positions: none recorded']), `CMS reference checks: ${reference}`, `Reviewer approval: ${approved}`];
    const title = [textValue(row.code) || 'Code', textValue(row.family), textValue(row.status).replace(/_/g, ' ')].filter(Boolean).join(' · ');
    return checkItem(row.approved === true ? '' : 'muted', row.approved === true ? 'circle-check' : 'info', title, '', lines.map(line => `<p>${escapeHtml(line)}</p>`).join(''));
  }).join('')}</div>`;
}

// The owner's trace of one document (GET /ops/api/encounters/<id>/trace, which answers the workspace owner only): each
// participant's requests with their identity, endpoint, models, usage, estimated cost and hashes, each reading in full,
// the retrieval traces and the reconciliation table.
function traceView(trace, id) {
  const data = trace && typeof trace === 'object' ? trace : {};
  const encounter = data.encounter && typeof data.encounter === 'object' ? data.encounter : {};
  const revision = data.revision && typeof data.revision === 'object' ? data.revision.number : data.revision;
  const meta = [Number.isInteger(revision) ? `Revision ${revision}` : '', 'Owner only', 'Synthetic documents only'].filter(Boolean).map(item => `<span>${escapeHtml(item)}</span>`).join('');
  const participants = objects(data.participants).map(participant => {
    const runs = objects(participant.runs);
    const name = textValue(participant.name);
    const title = lookup(PARTICIPANT_TITLES, name, [textValue(participant.label), textValue(participant.vendor)].filter(Boolean).join(' · ') || 'Participant');
    const model = textValue(participant.model);
    const about = [textValue(participant.vendor), model ? `model ${model}` : 'no model named (its API takes none)'].filter(Boolean).join(' · ');
    return `${sectionHeading(title, plural(runs.length, 'request', 'requests'))}<p class="section-description">${escapeHtml(about)}</p><div class="card-stack">${runs.length ? runs.map(traceRun).join('') : '<div class="check-list-card"><p class="harness-note">No request is recorded for this participant on this revision.</p></div>'}</div>`;
  }).join('');
  // harness@2: each assessment of the revision with the frozen phase-1 outputs it recorded (HARNESS.md 12.3)
  const assessments = Array.isArray(data.assessments) ? `${sectionHeading('Assessments of this revision', objects(data.assessments).length)}<div class="card-stack">${traceAssessments(data.assessments)}</div>` : '';
  // a new-path live assessment's interpretation section (the Gemini migration; FINAL 3.1): the record, the run, the inventory
  const interpretation = data.interpretation && typeof data.interpretation === 'object' && data.interpretation.engine === 'events'
    ? `${sectionHeading('Interpretation', textValue(data.interpretation.engine_version) || 'events')}<div class="card-stack">${interpretationCards(data.interpretation)}</div>` : '';
  return `<section class="view-entrance"><a class="back-link" href="#doc/${escapeHtml(encodeURIComponent(id))}">${icon('arrow')}Back to the review</a><div class="heading-row review-heading"><div><span class="eyebrow">TRACE · OWNER ONLY · SYNTHETIC</span><h1>${escapeHtml(textValue(encounter.title) || 'Document trace')}</h1><div class="review-meta">${meta}</div></div></div><p class="checks-disclaimer">Costs are estimated from fixed, dated vendor rates and are not reconciled to an invoice; Corti reports credits, not USD. Each hash names the exact stored request or raw response.</p>${participants}${interpretation}${assessments}${sectionHeading('Reference retrieval', objects(data.retrieval).length)}<div class="card-stack">${retrievalTraces(data.retrieval)}</div>${sectionHeading('Reconciliation', objects(data.reconciliation).length)}${traceReconciliation(data.reconciliation)}</section>`;
}

// What the trace page says when the API refuses it: a 403 plainly (the trace is the owner's), never as an error to retry.
function traceFailure(id, error) {
  const status = error?.status;
  const [title, detail, retry] = status === 403
    ? ['The trace is for the workspace owner.', 'Only the owner of this workspace can open the trace of a document, with each request, its usage and its estimated cost. The review itself is open to every member.', false]
    : status === 404
      ? ['This document is not available.', 'It does not exist, or it is not in your workspace.', false]
      : ['The trace could not be loaded.', textValue(error?.message) || 'Try again.', true];
  return `<section class="view-entrance"><a class="back-link" href="#doc/${escapeHtml(encodeURIComponent(id))}">${icon('arrow')}Back to the review</a><div class="check-list-card"><p class="empty-state"><strong>${escapeHtml(title)}</strong><br>${escapeHtml(detail)}</p>${retry ? '<p class="empty-state"><button type="button" class="button secondary" data-action="retry">Try again</button></p>' : ''}</div></section>`;
}

// --- browser wiring ------------------------------------------------------------------

class ApiError extends Error {
  constructor(message, status = 0, details = null) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function csrfToken() {
  return readCookie(document.cookie, 'cptstudio_csrf') || $('input[name="csrfmiddlewaretoken"]')?.value || '';
}

function goToLogin() {
  if (state.leaving) return;
  state.leaving = true;
  location.assign(`/login/?next=${encodeURIComponent(`/ops/${location.hash}`)}`);
}

async function api(path, { method = 'GET', json, form } = {}) {
  const headers = { Accept: 'application/json' };
  let body;
  if (method !== 'GET') headers['X-CSRFToken'] = csrfToken();
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
    throw new ApiError('The server could not be reached. Check the connection and try again.');
  }
  if (response.status === 401 || (response.redirected && new URL(response.url).pathname.startsWith('/login'))) {
    goToLogin();
    throw new ApiError('Your session has ended. Sign in again.', 401);
  }
  const isJson = (response.headers.get('Content-Type') || '').includes('application/json');
  const data = isJson ? await response.json().catch(() => null) : null;
  if (!response.ok) {
    const fallback = response.status === 403 ? 'The request was refused. Reload the page and try again.' : response.status === 404 ? 'Not found, or not in your workspace.' : `The request failed (HTTP ${response.status}).`;
    throw new ApiError(typeof data?.error === 'string' && data.error ? data.error : fallback, response.status, data?.details || null);
  }
  if (!data || typeof data !== 'object') throw new ApiError('The server returned an unexpected response.', response.status);
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
  const name = session.workspace?.name || 'Workspace';
  $('#workspaceName').textContent = name;
  $('#workspaceSubtitle').textContent = session.workspace?.subtitle || 'Synthetic demonstration workspace';
  $('#workspaceAvatar').textContent = ([...name.trim()][0] || '').toUpperCase();
  const label = session.user?.label || session.user?.username || 'Signed in';
  const initials = session.user?.initials || label.split(/\s+/).filter(Boolean).slice(0, 2).map(word => [...word][0]).join('').toUpperCase();
  $('#profileAvatar').textContent = initials;
  $('#topAvatar').textContent = initials;
  $('#profileName').textContent = label;
  $('#profileRole').textContent = lookup({ owner: 'Owner', reviewer: 'Reviewer', viewer: 'Viewer' }, session.role, 'Member');
  $('#aboutRelease').textContent = session.release ? `Release ${session.release}.` : '';
  setCount('#documentsCount', session.counts?.documents);
  setCount('#queueCount', session.counts?.queue);
  $('#specialty').options[0].textContent = categoryName();
}

async function loadSession() {
  try {
    state.session = await api('/ops/api/session');
    renderSession(state.session);
  } catch (error) {
    if (error.status !== 401) toast(`The workspace could not be loaded. ${error.message}`);
  }
  return state.session;
}

function setActiveNav(name) {
  const active = name === 'doc' || name === 'trace' ? 'documents' : name;
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

function route() {
  const next = parseRoute(location.hash);
  const token = ++state.routeToken;
  stopPolling();
  if (next.name !== 'doc' || next.id !== state.doc?.id) {
    state.doc = null;
    state.docKey = '';
    state.layout = null;
    state.currentTab = 'codes';
    state.selectedEvidence = [];
  }
  state.route = next;
  $('#breadcrumbCurrent').textContent = ROUTE_TITLES[next.name];
  setActiveNav(next.name);
  closeNavigation();
  window.scrollTo({ top: 0, behavior: 'instant' });
  if (next.name === 'doc') return showDocument(next.id, token);
  if (next.name === 'trace') return showTrace(next.id, token);
  if (next.name === 'how-it-works') {
    $('#main').innerHTML = howItWorksView();
    return undefined;
  }
  return showList(next.name, token);
}

async function showList(name, token) {
  $('#main').innerHTML = name === 'workspace' ? overviewView() : documentsView(name);
  let encounters;
  try {
    ({ encounters } = await api('/ops/api/encounters'));
    if (!Array.isArray(encounters)) throw new ApiError('The server returned an unexpected document list.');
  } catch (error) {
    if (token !== state.routeToken) return;
    $('#documentsTable').innerHTML = `${LIST_HEADER}<p class="empty-state">${escapeHtml(`Documents could not be loaded. ${error.message}`)}</p>`;
    if ($('#listDescription')) $('#listDescription').textContent = 'Documents could not be loaded.';
    if ($('#recentInvite')) $('#recentInvite').innerHTML = '';
    return;
  }
  if (token !== state.routeToken) return;
  $('#documentsTable').innerHTML = listBody(name, encounters);
  if ($('#listDescription')) $('#listDescription').textContent = listDescription(name, encounters);
  if ($('#recentInvite')) $('#recentInvite').innerHTML = inviteMarkup(encounters);
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

function showDocument(id, token) {
  if (!UUID.test(id)) {
    $('#main').innerHTML = messageView('This document is not available.', 'The address does not name a document in this workspace.');
    return undefined;
  }
  $('#main').innerHTML = '<section class="view-entrance"><p class="empty-state">Loading the review…</p></section>';
  return loadDocument(id, token, false);
}

// The owner's trace page: drawn once from GET /ops/api/encounters/<id>/trace, never polled. The link to it is shown to the
// owner only, and the API refuses every other role (403), which the page says plainly.
async function showTrace(id, token) {
  if (!UUID.test(id)) {
    $('#main').innerHTML = messageView('This document is not available.', 'The address does not name a document in this workspace.');
    return;
  }
  $('#main').innerHTML = '<section class="view-entrance"><p class="empty-state">Loading the trace…</p></section>';
  let trace;
  try {
    trace = await api(`/ops/api/encounters/${encodeURIComponent(id)}/trace`);
  } catch (error) {
    if (token === state.routeToken) $('#main').innerHTML = traceFailure(id, error);
    return;
  }
  if (token === state.routeToken) $('#main').innerHTML = traceView(trace, id);
}

async function loadDocument(id, token, silent) {
  clearTimeout(state.poll.timer);
  let doc;
  try {
    doc = await api(`/ops/api/encounters/${encodeURIComponent(id)}`);
  } catch (error) {
    if (token !== state.routeToken) return;
    if (silent && state.doc) {
      if (state.doc.pipeline?.busy) {
        state.poll.errors += 1;
        schedulePoll(token);
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
  if (token !== state.routeToken) return;
  state.poll.errors = 0;
  renderDocument(doc, !silent);
  schedulePoll(token);
}

function schedulePoll(token) {
  clearTimeout(state.poll.timer);
  if (!state.doc?.pipeline?.busy) {
    state.poll.count = 0;
    return;
  }
  const delay = pollDelay(state.poll.count, state.poll.errors);
  state.poll.count += 1;
  const id = state.doc.id;
  state.poll.timer = setTimeout(() => loadDocument(id, token, true), delay);
}

async function refreshDocument() {
  if (state.route?.name !== 'doc') return;
  state.poll.count = 0;
  state.poll.errors = 0;
  await loadDocument(state.route.id, state.routeToken, true);
}

function focusTarget() {
  const element = document.activeElement;
  if (!element || !$('#main').contains(element)) return null;
  if (element.dataset.proposal) return { proposal: element.dataset.proposal };
  if (element.dataset.tab) return { tab: element.dataset.tab };
  return element.id ? { id: element.id } : null;
}

function restoreFocus(target) {
  if (!target) return;
  if (target.proposal) {
    const buttons = $$('[data-proposal]').filter(element => element.dataset.proposal === target.proposal);
    const card = $$('.code-card').find(element => element.id === `card-${target.proposal}`);
    (buttons[0] || card)?.focus({ preventScroll: true });
  } else if (target.tab) {
    $(`#tab-${target.tab}`)?.focus({ preventScroll: true });
  } else {
    document.getElementById(target.id)?.focus({ preventScroll: true });
  }
}

function renderDocument(doc, fresh) {
  const key = JSON.stringify(doc);
  if (!fresh && key === state.docKey) return;
  const keep = fresh ? null : { source: $('#sourceScroll')?.scrollTop || 0, window: window.scrollY, focus: focusTarget() };
  state.doc = doc;
  state.docKey = key;
  state.layout = documentLayout(doc);
  if (!doc.assessment || !tabsFor(doc).some(([id]) => id === state.currentTab)) state.currentTab = 'codes';
  $('#main').innerHTML = reviewView(doc, state.layout, state.currentTab, fresh);
  if (keep) {
    if ($('#sourceScroll')) $('#sourceScroll').scrollTop = keep.source;
    window.scrollTo({ top: keep.window, behavior: 'instant' });
    restoreFocus(keep.focus);
  }
  if (state.selectedEvidence.length) applyHighlight(state.selectedEvidence);
  updatePageNumber();
}

function selectTab(tab, focus = false) {
  if (!tabsFor(state.doc).some(([id]) => id === tab) || !state.doc?.assessment || !$('#resultContent')) return;
  state.currentTab = tab;
  $$('[role="tab"]').forEach(button => {
    const selected = button.dataset.tab === tab;
    button.setAttribute('aria-selected', String(selected));
    button.tabIndex = selected ? 0 : -1;
  });
  const panel = $('#resultContent');
  panel.setAttribute('aria-labelledby', `tab-${tab}`);
  panel.innerHTML = tabContent(state.doc, tab, state.layout);
  if (tab === 'codes') markChips(new Set(state.selectedEvidence));
  if (focus) $(`#tab-${tab}`).focus({ preventScroll: true });
}

function evidenceKeys(element) {
  return (element.dataset.keys || element.dataset.evidence || '').split(' ').filter(Boolean);
}

function markChips(wanted) {
  $$('.evidence-chip[data-evidence]').forEach(chip => chip.classList.toggle('selected', wanted.has(chip.dataset.evidence)));
}

function applyHighlight(keys) {
  const wanted = new Set(keys);
  let first = null;
  $$('.evidence-mark').forEach(mark => {
    const selected = evidenceKeys(mark).some(key => wanted.has(key));
    mark.classList.toggle('selected', selected);
    if (selected && !first) first = mark;
  });
  markChips(wanted);
  return first;
}

function highlightEvidence(keys, scroll = true) {
  state.selectedEvidence = keys;
  if (state.currentTab !== 'codes') selectTab('codes');
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

function findProposal(id) {
  return (state.doc?.assessment?.proposals || []).find(proposal => proposal.id === id) || null;
}

async function openReview(proposalId, action) {
  const proposal = findProposal(proposalId);
  if (!proposal || !REVIEW_COPY[action]) return;
  if (!state.session && !(await loadSession())) {
    toast('Your identity could not be confirmed, so no decision can be recorded. Reload the page and try again.');
    return;
  }
  const agent = isAgent();
  const copy = REVIEW_COPY[action];
  const revision = state.doc.revision?.number;
  const text = {
    approve: agent ? `This approval is recorded as an agent-executed synthetic review, with the agent's identity and the time, against revision ${revision} of this document. A changed source invalidates it.` : `Your approval is recorded with your identity and the time, against revision ${revision} of this document. A changed source invalidates it.`,
    reject: 'A rejected code is excluded from approved results. Add a note so the next reviewer knows why.',
    reinstate: 'This code was excluded by a documentation check. Reinstating records your judgement and makes it reviewable; it does not approve it.',
    confirm: 'A documentation check read this service as not performed on the date of service. Confirming records your judgement that the exclusion is right. The reviewed report waits until each such code is confirmed or reinstated.',
  }[action];
  const notVerified = (proposal.checks || []).filter(check => check.status === 'not_verified').map(check => check.label);
  state.review = { proposalId, action };
  $('#reviewEyebrow').textContent = copy.eyebrow;
  $('#reviewTitle').textContent = copy.title;
  $('#reviewCopy').textContent = text;
  $('#reviewCode').textContent = proposal.code;
  $('#reviewFamily').textContent = proposal.family_label || proposal.family || '';
  $('#reviewDescriptor').textContent = proposal.descriptor?.label || 'Description withheld.';
  $('#reviewAckLabel').hidden = action !== 'approve';
  $('#reviewAcknowledgement').checked = false;
  $('#reviewAckText').textContent = attestationText(state.session);
  $('#reviewNote').value = '';
  $('#reviewNotice').textContent = notVerified.length ? `Still not verified for this code: ${notVerified.join('; ')}.` : 'A review decision records a judgement; it is not billing advice.';
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
  return api(`/ops/api/encounters/${encodeURIComponent(state.doc.id)}/decisions`, { method: 'POST', json: body });
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
    showError('reviewError', 'Confirm that you reviewed the source evidence for this code.');
    return undefined;
  }
  return guarded('review', async () => {
    const button = $('#saveReview');
    setBusy(button, true);
    hideError('reviewError');
    try {
      await postDecision({ proposal_id: review.proposalId, action: review.action, note: $('#reviewNote').value.trim(), acknowledgement: review.action === 'approve' ? $('#reviewAckText').textContent : '' });
      const code = findProposal(review.proposalId)?.code || 'the code';
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
      await afterChange(`Decision undone for ${findProposal(proposalId)?.code || 'the code'}.`);
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

function resetUpload() {
  state.upload = { file: null, paste: false, busy: false };
  $('#uploadForm').reset();
  setUploadFile(null);
  setPasteMode(false);
  hideError('uploadError');
  $('#specialty').options[0].textContent = categoryName();
}

function openUpload(file) {
  if (state.upload.busy) return openDialog('uploadDialog');
  resetUpload();
  if (file) setUploadFile(file);
  return openDialog('uploadDialog');
}

function setUploadFile(file) {
  hideError('uploadError');
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
  $('#fileFields').hidden = paste;
  $('#pasteField').hidden = !paste;
  $('#pasteToggle').textContent = paste ? 'Upload a file instead' : 'Paste text instead';
  $('#pasteToggle').setAttribute('aria-expanded', String(paste));
  hideError('uploadError');
}

function uploadForm() {
  const form = new FormData();
  if (state.upload.paste) {
    const text = $('#pasteText').value;
    if (!text.trim()) return 'Paste the clinical text, or switch back to uploading a file.';
    if (codePoints(text) > MAX_PASTE_CHARS) return 'The pasted text is longer than 400,000 characters. Upload it as a file instead.';
    form.append('text', text);
  } else {
    if (!state.upload.file) return 'Choose a PDF, DOCX or TXT document, or paste the text instead.';
    form.append('file', state.upload.file, state.upload.file.name);
  }
  const serviceDate = $('#serviceDate').value;
  if (serviceDate && !parseIsoDate(serviceDate)) return 'Enter the service date as a valid date, or leave it blank.';
  if (!$('#syntheticAttestation').checked) return 'Confirm that the document is synthetic and contains no real patient information.';
  if (serviceDate) form.append('service_date', serviceDate);
  form.append('synthetic_attestation', 'yes');
  return form;
}

async function submitUpload(event) {
  event.preventDefault();
  if (state.upload.busy) return;
  const form = uploadForm();
  if (typeof form === 'string') {
    showError('uploadError', form);
    return;
  }
  const button = $('#startReview');
  state.upload.busy = true;
  setBusy(button, true);
  hideError('uploadError');
  try {
    const created = await api('/ops/api/encounters', { method: 'POST', form });
    if (!UUID.test(String(created.id || ''))) throw new ApiError('The server did not return a document identifier.');
    state.upload.busy = false;
    closeDialog('uploadDialog');
    toast('Document received. Processing has started.');
    loadSession();
    location.hash = `doc/${created.id}`;
  } catch (error) {
    showError('uploadError', error.message);
  } finally {
    state.upload.busy = false;
    setBusy(button, false);
  }
}

function openContext() {
  if (!state.doc) return;
  const values = state.doc.context?.user_values || {};
  $('#contextServiceDate').value = parseIsoDate(values.service_date) ? values.service_date : '';
  $('#contextSetting').value = lookup(SETTING_LABELS, values.setting, null) ? values.setting : '';
  $('#contextBilling').value = lookup(BILLING_LABELS, values.billing_context, null) ? values.billing_context : '';
  hideError('contextError');
  openDialog('contextDialog');
}

function submitContext(event) {
  event.preventDefault();
  if (!state.doc) return undefined;
  const body = { service_date: $('#contextServiceDate').value, setting: $('#contextSetting').value, billing_context: $('#contextBilling').value };
  if (body.service_date && !parseIsoDate(body.service_date)) {
    showError('contextError', 'Enter the service date as a valid date, or leave it blank.');
    return undefined;
  }
  const current = state.doc.context?.user_values || {};
  if (Object.keys(body).every(name => body[name] === (current[name] || ''))) {
    closeDialog('contextDialog');
    toast('No context change to save.');
    return undefined;
  }
  return guarded('context', async () => {
    const button = $('#saveContext');
    setBusy(button, true);
    hideError('contextError');
    try {
      await api(`/ops/api/encounters/${encodeURIComponent(state.doc.id)}/context`, { method: 'POST', json: body });
      closeDialog('contextDialog');
      await afterChange('Context saved. The codes are being re-checked.');
    } catch (error) {
      showError('contextError', error.message);
    } finally {
      setBusy(button, false);
    }
  });
}

function openAddendum(clarificationId) {
  const clarification = (state.doc?.clarifications || []).find(item => item.id === clarificationId) || null;
  state.addendum = { clarificationId: clarification?.id || null };
  $('#addendumQuestion').textContent = clarification?.question || '';
  $('#addendumQuestion').hidden = !clarification;
  $('#addendumText').value = '';
  $('#addendumAttestation').checked = false;
  hideError('addendumError');
  openDialog('addendumDialog');
}

function submitAddendum(event) {
  event.preventDefault();
  if (!state.doc || !state.addendum) return undefined;
  const text = $('#addendumText').value;
  if (!text.trim()) {
    showError('addendumError', 'Write the addendum text.');
    return undefined;
  }
  if (codePoints(text.trim()) > MAX_ADDENDUM_CHARS) {
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
      await api(`/ops/api/encounters/${encodeURIComponent(state.doc.id)}/addenda`, { method: 'POST', json: { text, clarification_id: state.addendum.clarificationId, synthetic_attestation: 'yes' } });
      closeDialog('addendumDialog');
      await afterChange('Addendum added as a new revision. Processing has started.');
    } catch (error) {
      showError('addendumError', error.message);
    } finally {
      setBusy(button, false);
    }
  });
}

function stopProcessing(button) {
  if (!state.doc) return undefined;
  return guarded('stop', async () => {
    setBusy(button, true);
    try {
      await api(`/ops/api/encounters/${encodeURIComponent(state.doc.id)}/stop`, { method: 'POST', json: {} });
      await afterChange('Stop requested. Queued stages are being cancelled.');
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
      await api(`/ops/api/encounters/${encodeURIComponent(state.doc.id)}/resume`, { method: 'POST', json: {} });
      await afterChange('Processing resumed.');
    } catch (error) {
      toast(error.message);
      setBusy(button, false);
    }
  });
}

function requestSecondReview(button) {
  if (!state.doc) return undefined;
  return guarded('second-review', async () => {
    setBusy(button, true);
    try {
      await api(`/ops/api/encounters/${encodeURIComponent(state.doc.id)}/second-review`, { method: 'POST', json: {} });
      await afterChange('Second review requested.');
    } catch (error) {
      toast(error.message);
      setBusy(button, false);
    }
  });
}

// What a confirmation did (POST .../confirm answers the confirmation and its effect, HARNESS.md 12.5): a date of
// service entered as the member's date, or a re-assessment that reads the finding. Neither approves anything.
function confirmedMessage(result) {
  const confirmation = result?.confirmation && typeof result.confirmation === 'object' ? result.confirmation : result || {};
  const fact = lookup(FINDING_FACTS, confirmation.fact, 'The finding');
  const value = textValue(confirmation.value);
  if (result?.effect === 'context') return `Confirmed: ${fact.toLowerCase()} ${value} entered as your date, and the codes are being re-checked. Nothing was approved.`;
  if (result?.effect === 'reassessment') return `Confirmed: ${fact.toLowerCase()} ${value}. The codes are being re-checked with the confirmed finding; nothing was approved.`;
  return 'Confirmation recorded. Nothing was approved.';
}

// A reviewer's confirmation of one verified candidate (HARNESS.md 11.3, 12.5): the attestation must be ticked, and what
// is sent is the candidate's served attestation, never text rebuilt here. A member act: nothing ever confirms by
// itself.
function confirmFinding(button) {
  if (!state.doc || !button) return undefined;
  const clarificationId = button.dataset.clarification;
  const candidateId = button.dataset.confirm;
  const box = button.closest('.confirm-finding');
  const error = box?.querySelector('.form-error');
  const fail = message => {
    if (!error) return toast(message);
    error.textContent = message;
    error.hidden = false;
    return undefined;
  };
  const question = (state.doc.clarifications || []).find(item => item?.id === clarificationId);
  const candidate = objects(question?.candidates).find(item => item.id === candidateId);
  if (!candidate || candidate.verified !== true || !textValue(candidate.attestation) || state.doc.permissions?.can_confirm !== true) {
    return fail('This answer can no longer be confirmed here. Reload the page.');
  }
  if (box?.querySelector('input[data-attest]')?.checked !== true) return fail('Tick the attestation first: confirm that you read this passage in the source document.');
  return guarded(`confirm:${clarificationId}`, async () => {
    setBusy(button, true);
    if (error) error.hidden = true;
    try {
      const result = await api(`/ops/api/encounters/${encodeURIComponent(state.doc.id)}/clarifications/${encodeURIComponent(clarificationId)}/confirm`, { method: 'POST', json: { candidate_id: candidate.id, attestation: candidate.attestation } });
      await afterChange(confirmedMessage(result));
    } catch (failure) {
      fail(failure.message);
      setBusy(button, false);
    }
  });
}

function submitReconcile(form) {
  if (!state.doc) return undefined;
  const note = $('#reconcileNote').value.trim();
  if (codePoints(note) < MIN_RECONCILE_CHARS) {
    showError('reconcileError', `Describe how the unknown outcome was reconciled (at least ${MIN_RECONCILE_CHARS} characters).`);
    return undefined;
  }
  return guarded('reconcile', async () => {
    const button = form.querySelector('button[type="submit"]');
    setBusy(button, true);
    hideError('reconcileError');
    try {
      await api(`/ops/api/encounters/${encodeURIComponent(state.doc.id)}/reconcile`, { method: 'POST', json: { provider_run_id: form.dataset.run, note } });
      await afterChange('Reconciliation recorded.');
    } catch (error) {
      showError('reconcileError', error.message);
      setBusy(button, false);
    }
  });
}

// The operator's recorded retry of a failed reading (POST /ops/api/encounters/<id>/retry-reading, FINAL 11.3): the
// override is sent only when ticked, and recorded with the operator's name.
function submitRetryReading(form) {
  if (!state.doc) return undefined;
  const override = $('#retryOverride')?.checked === true;
  return guarded('retry-reading', async () => {
    const button = form.querySelector('button[type="submit"]');
    setBusy(button, true);
    hideError('retryReadingError');
    try {
      await api(`/ops/api/encounters/${encodeURIComponent(state.doc.id)}/retry-reading`, { method: 'POST', json: { override } });
      await afterChange(RETRY_DONE);
    } catch (error) {
      showError('retryReadingError', error.message);
      setBusy(button, false);
    }
  });
}

// The recorded release of the interpreter hold (POST /ops/api/interpreter {note}, FINAL 11.2): the note says why it may end.
function submitHoldRelease(form) {
  const note = $('#releaseHoldNote').value.trim();
  if (!note) {
    showError('releaseHoldError', 'Say why the hold may end: the release is recorded with this note.');
    return undefined;
  }
  return guarded('release-hold', async () => {
    const button = form.querySelector('button[type="submit"]');
    setBusy(button, true);
    hideError('releaseHoldError');
    try {
      await api('/ops/api/interpreter', { method: 'POST', json: { note } });
      await afterChange(HOLD_RELEASED);
    } catch (error) {
      showError('releaseHoldError', error.message);
      setBusy(button, false);
    }
  });
}

function openExport() {
  if (!state.doc) return;
  const readiness = state.doc.readiness || {};
  $('#exportStatus').classList.toggle('reviewed', readiness.reviewed === true);
  $('#exportStatus').textContent = exportStatusText(state.doc);
  $('#exportOptions').innerHTML = exportOptions(readiness);
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
    options.forEach(option => setBusy(option, true));
    hideError('exportError');
    try {
      const report = await api(`/ops/api/encounters/${encodeURIComponent(state.doc.id)}/reports`, { method: 'POST', json: { kind, fmt } });
      const url = safeDownloadUrl(report.download_url);
      if (!url) throw new ApiError('The server returned an unexpected download address, so nothing was downloaded.');
      startDownload(url, report.filename);
      $('#exportStatus').textContent = `${exportStatusText(state.doc)} Downloading ${report.filename || 'the report'}.`;
      refreshDocument();
    } catch (error) {
      const blockers = Array.isArray(error.details?.blockers) ? error.details.blockers.filter(Boolean) : [];
      showError('exportError', blockers.length ? `${error.message} ${blockers.join('; ')}.` : error.message);
    } finally {
      options.forEach(option => setBusy(option, false));
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
  const tab = target.closest('[data-tab]');
  if (tab) {
    selectTab(tab.dataset.tab, true);
    return;
  }
  const decision = target.closest('[data-decision]');
  if (decision) {
    handleDecision(decision.dataset.decision, decision.dataset.proposal, decision);
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
    'edit-context': openContext,
    addendum: () => openAddendum(action.dataset.clarification),
    stop: () => stopProcessing(action),
    resume: () => resumeProcessing(action),
    'second-review': () => requestSecondReview(action),
    'confirm-finding': () => confirmFinding(action),
    retry: route,
  })[action.dataset.action]?.();
}

// The console's own forms: a reconciliation, the retry of a failed reading, the release of the interpreter hold.
function onSubmit(event) {
  const handler = { reconcileForm: submitReconcile, retryReadingForm: submitRetryReading, releaseHoldForm: submitHoldRelease }[event.target?.id];
  if (!handler) return undefined;
  event.preventDefault();
  return handler(event.target);
}

// The confirm action is offered once its attestation is ticked.
function onChange(event) {
  const box = event.target.matches?.('input[data-attest]') ? event.target.closest('.confirm-finding') : null;
  const button = box?.querySelector('[data-action="confirm-finding"]');
  if (button && !button.hasAttribute('aria-busy')) button.disabled = !event.target.checked;
}

function onKeydown(event) {
  if (event.key === 'Escape') closeNavigation();
  if (!event.target.matches('[role="tab"]') || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault();
  const tabs = $$('[role="tab"]');
  const current = tabs.indexOf(event.target);
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
  selectTab(tabs[next].dataset.tab, true);
}

function bindDialogs() {
  $('#uploadForm').addEventListener('submit', submitUpload);
  $('#reviewForm').addEventListener('submit', submitReview);
  $('#contextForm').addEventListener('submit', submitContext);
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
  document.addEventListener('keydown', onKeydown);
  document.addEventListener('input', event => { if (event.target.id === 'documentSearch') applySearch(); });
  document.addEventListener('submit', event => onSubmit(event));
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
  window.matchMedia('(max-width:760px)').addEventListener('change', closeNavigation);
  loadSession().then(route);
}

if (typeof module === 'object' && module.exports) {
  module.exports = {
    escapeHtml, lookup, parseIsoDate, formatDate, formatTimestamp, readCookie, safeDownloadUrl, pollDelay, parseRoute,
    passagesLabel, codeUnitOffsets, mergeSpans, pageRanges, paragraphRanges, paragraphPieces, layoutDocument,
    factValue, metaFact, exportStatusText, documentLayout, reviewView, documentRow, listBody, listDescription, listedDateEvidence,
    inviteMarkup, overviewView, documentsView, howItWorksView, exportOptions, state, QUEUE_STATES, decisionLine,
    hasAgentDecision, candidateDecision, ACKNOWLEDGEMENTS, emptySelectionCopy, attestationText,
    codingBanner, documentedServices, evidenceChips, secondReviewUnread, inQueue, candidateGroups, serviceDateChip,
    serviceDateMeta, participantsCard, codeStatusLines, participantPositions, retrievalSection, participantText, traceView,
    traceFailure, showTrace, STAGES, PARTICIPANT_STATES, REFERENCE_STATES, RETRIEVAL_FAILED, DESCRIPTOR_LIKE,
    DESCRIPTOR_WITHHELD,
    PEER_STAGES, PEER_STATES, PEER_NOT_RUN, CANDIDATE_NOTE, harness2, phasedJobs, peerPhaseOnly, confirmedFrom, locatedBy,
    candidateAnswers, referenceLists, confirmedFindings, confirmFinding, confirmedMessage, onChange,
    // the Gemini migration: the interpretation tab, the hold, the retry of a failed reading, the interpreter's rows
    TABS, INTERPRETATION_TAB, INTERPRET_STAGE, DERIVE_STAGE_LABEL, EVENT_FACTS, FINDING_FACTS, RUN_PROVIDERS, RUN_PURPOSES,
    RETRY_DONE, HOLD_RELEASED, interpreted, tabsFor, stagesFor, interpretationPanel, interpretationCards, attributeLine,
    interpreterHoldCard, failedReading, retryReadingCard, stateCards, progressCard, activityPanel, usageText, onSubmit,
    submitRetryReading, submitHoldRelease,
  };
}
if (typeof document !== 'undefined') boot();
