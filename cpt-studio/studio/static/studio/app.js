'use strict';
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
const REPORT_URL = /^\/api\/reports\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\/download$/i;
const PARAGRAPH_BREAK = /\n(?:[^\S\n]*\n)+/g;
// States that wait on a member: a clarification, a review decision, or a reconciliation.
const QUEUE_STATES = new Set(['needs_clarification', 'ready_for_review', 'provider_unknown']);
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const NUMBER_WORDS = ['No', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten'];
const HTML_ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;', '`': '&#x60;' };

const SETTING_LABELS = { office: 'Office', hospital_outpatient: 'Hospital outpatient department', asc: 'Ambulatory surgery center', inpatient: 'Inpatient', emergency: 'Emergency department', telehealth: 'Telehealth' };
const BILLING_LABELS = { professional: 'Professional', facility: 'Facility' };
const PATIENT_LABELS = { new: 'New patient', established: 'Established patient' };
const SOURCE_KINDS = { pdf: 'PDF', docx: 'DOCX', txt: 'TXT', paste: 'Pasted text', addendum: 'Addendum' };
const METHOD_LABELS = { txt: 'Text file', docx: 'Word document', 'pdf-text': 'PDF text layer', 'pdf-ocr': 'PDF read with OCR', 'pdf-mixed': 'PDF text layer and OCR', paste: 'Pasted text', addendum: 'Text with addendum' };
const STATE_TONES = { ready_for_review: 'green', reviewed: 'green', needs_clarification: 'amber', provider_unknown: 'amber', provider_failed: 'amber', extraction_failed: 'amber' };
const STAGES = [['extract', 'Read the original document'], ['analyze', 'Identify documented services and context'], ['predict', 'Request CPT proposals from the provider'], ['assess', 'Check proposals against references and rules']];
const SECOND_REVIEW_STAGE = ['review2', 'Second provider review (asked for by a reviewer)'];
const STAGE_STATES = { queued: 'Waiting', running: 'In progress', succeeded: 'Done', failed: 'Failed', unknown: 'Outcome unknown', cancelled: 'Stopped' };
const STAGE_LOOKS = { queued: ['muted', 'clock'], running: ['pending running', 'clock'], succeeded: ['', 'circle-check'], failed: ['pending', 'close'], unknown: ['pending', 'info'], cancelled: ['muted', 'stop'] };
const CHECK_LABELS = { pass: 'Pass', warn: 'Warning', fail: 'Fail', not_verified: 'Not verified', not_applicable: 'Not applicable', info: 'Information' };
const CHECK_LOOKS = { pass: ['', 'circle-check'], info: ['muted', 'info'], not_applicable: ['muted', 'info'], warn: ['pending', 'info'], fail: ['pending', 'close'], not_verified: ['pending', 'clock'] };
const RUN_STATES = { reserved: 'Reserved', sending: 'Sending', succeeded: 'Succeeded', failed: 'Failed', unknown: 'Outcome unknown', not_sent: 'Not sent', cancelled: 'Cancelled' };
const DECISION_TITLES = { approve: 'Approved', reject: 'Rejected', reinstate: 'Reinstated for review', confirm: 'Exclusion confirmed', revoke: 'Revoked the decision on' };
const ACTION_BUTTONS = [['approve', 'primary', 'Approve', 'check'], ['reject', 'secondary', 'Reject', ''], ['reinstate', 'secondary', 'Reinstate for review', ''], ['confirm', 'secondary', 'Confirm exclusion', ''], ['revoke', 'secondary', 'Undo decision', '']];
const TABS = [['codes', 'Suggestions'], ['checks', 'Checks'], ['timeline', 'Activity']];
const ROUTE_TITLES = { workspace: 'Overview', documents: 'Documents', queue: 'Review queue', 'how-it-works': 'How it works', doc: 'Document review' };
const ACKNOWLEDGEMENTS = {
  human: 'I read the whole source document, not only the cited passages, and it supports this code as a service performed at this encounter. The documentation checks can miss wording they do not recognise. This synthetic review is not clinical approval or billing advice.',
  agent: 'I am an automated agent. I read the whole source document, not only the cited passages, and it supports this code as a service performed at this encounter. The documentation checks can miss wording they do not recognise. This agent-executed synthetic review is not clinical approval or billing advice.',
};
// The attestation the server accepts is the one /api/session serves (round 5, bypass:4); the built-in copy above
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
  return { name: lookup(ROUTE_TITLES, path, null) && path !== 'doc' ? path : 'workspace' };
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

function paragraphPieces(text, start, end, marks) {
  const pieces = [];
  let cursor = start;
  for (const mark of marks) {
    if (mark.end <= start || mark.start >= end) continue;
    const from = Math.max(mark.start, start);
    const to = Math.min(mark.end, end);
    if (from > cursor) pieces.push({ text: text.slice(cursor, from), keys: null });
    pieces.push({ text: text.slice(from, to), keys: mark.keys });
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
  return {
    pages: pageRanges(pages, length, unit, source.length).map(page => ({
      page: page.page,
      paragraphs: paragraphRanges(source, page.start, page.end).map(([from, to]) => paragraphPieces(source, from, to, marks)),
    })),
    unlocated,
  };
}

function factValue(fact, labels, isDate = false) {
  if (!fact) return 'Not documented';
  if (fact.origin === 'conflict') return 'Conflicting values documented';
  if (fact.origin === 'missing' || fact.value == null || fact.value === '' || fact.value === 'not_documented') return 'Not documented';
  const value = isDate ? (formatDate(fact.value, true) || String(fact.value)) : lookup(labels, fact.value, String(fact.value));
  return fact.origin === 'user' ? `${value} (entered)` : value;
}

function metaFact(fact, labels, name, isDate = false) {
  if (!fact || fact.origin === 'missing' || fact.value == null || fact.value === '') return `${name} not documented`;
  if (fact.origin === 'conflict') return `${name} conflict`;
  const value = isDate ? (formatDate(fact.value) || String(fact.value)) : lookup(labels, fact.value, String(fact.value));
  return fact.origin === 'user' ? `${value} (entered)` : value;
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

function documentRow(encounter) {
  const tone = lookup(STATE_TONES, encounter.state, 'gray');
  const families = Array.isArray(encounter.families) && encounter.families.length ? encounter.families.join(' · ') : categoryName();
  const kind = lookup(SOURCE_KINDS, encounter.source_kind, encounter.source_kind ? String(encounter.source_kind).toUpperCase() : '');
  const open = Number.isInteger(encounter.open_clarifications) && encounter.open_clarifications > 0 ? plural(encounter.open_clarifications, 'open question', 'open questions') : '';
  const meta = [kind, families, open].filter(Boolean).join(' · ');
  return `<a class="document-row" href="#doc/${escapeHtml(encodeURIComponent(encounter.id))}"><span class="doc-row-main"><span class="doc-file-icon${tone === 'amber' ? ' amber' : ''}">${icon('file')}</span><span><strong>${escapeHtml(encounter.title || 'Untitled document')}</strong><small>${escapeHtml(meta)}</small></span></span><span>${stateBadge(encounter.state, encounter.state_label)}</span><span class="doc-row-date">${escapeHtml(formatDate(encounter.service_date) || 'Not documented')}</span>${icon('chevron', 'row-arrow')}</a>`;
}

function listRows(name, encounters) {
  if (name === 'queue') return encounters.filter(item => QUEUE_STATES.has(item.state));
  return name === 'workspace' ? encounters.slice(0, 5) : encounters;
}

function listBody(name, encounters) {
  const rows = listRows(name, encounters);
  const empty = { workspace: 'No documents yet. Start with a synthetic GI document.', documents: 'No documents yet. Use New document to upload a synthetic GI document or paste its text.', queue: 'Nothing is waiting for review.' }[name];
  return LIST_HEADER + (rows.length ? rows.map(documentRow).join('') : `<p class="empty-state">${escapeHtml(empty)}</p>`);
}

function listDescription(name, encounters) {
  if (name === 'queue') {
    const count = listRows('queue', encounters).length;
    return count ? `${count === 1 ? 'One document needs' : `${count} documents need`} a clarification, a review decision or a reconciliation.` : 'No document is waiting for a clarification, a review decision or a reconciliation.';
  }
  return `${plural(encounters.length, 'synthetic document', 'synthetic documents')} in this workspace.`;
}

function inviteMarkup(encounters) {
  const recent = encounters?.[0];
  if (encounters === null) return `<span class="sample-icon">${icon('file')}</span><span class="sample-text"><strong>Loading recent documents…</strong><p>One moment.</p></span>`;
  if (!recent) return `<span class="sample-icon">${icon('file')}</span><span class="sample-text"><strong>No documents yet</strong><p>Upload a synthetic GI document to see proposals beside the source.</p></span><button type="button" class="button secondary" data-action="upload">New document ${icon('plus')}</button>`;
  const detail = ['Most recent', recent.state_label, formatDate(recent.service_date) || 'service date not documented'].filter(Boolean).join(' · ');
  return `<span class="sample-icon">${icon('file')}</span><span class="sample-text"><strong>${escapeHtml(recent.title || 'Untitled document')}</strong><p>${escapeHtml(detail)}</p></span><button type="button" class="button secondary" data-open="${escapeHtml(recent.id)}">Open review ${icon('arrow')}</button>`;
}

function overviewView() {
  return `<section class="view-entrance"><div class="heading-row home-heading"><div><span class="eyebrow">A CLEARER VIEW OF EVERY CODE</span><h1>Precision starts<br>with the <em>evidence.</em></h1><p>A focused workspace to turn clinical documentation into evidence-backed CPT suggestions.</p></div><div class="heading-actions"><span class="only-tag">CPT ONLY</span><button type="button" class="button primary" data-action="upload" aria-label="New document">${icon('plus')}<span class="desktop-label">New document</span></button></div></div>
  <div class="home-grid"><section class="upload-panel"><div class="panel-heading">${icon('file')}<h2>Start a coding review</h2><span class="small-badge">One encounter at a time</span></div><button type="button" class="drop-zone" id="overviewDrop" data-action="upload"><span class="upload-icon">${icon('upload')}</span><strong>Bring the original document.</strong><span>Choose a file, drop it here or paste the text</span><span>PDF, DOCX or TXT</span></button><div class="upload-footnote">${icon('info')}<span>Synthetic documents only. Do not upload real patient information.</span></div><div class="sample-invite" id="recentInvite">${inviteMarkup(null)}</div></section>
  <aside class="story-panel"><span class="eyebrow">BUILT AROUND THE CLINICAL STORY</span><h2>A clearer path.<br>From note to code.</h2><ol class="workflow-list"><li><span class="workflow-number">01</span><span><strong>Read the whole note</strong><p>Begin with the original documentation and encounter context.</p></span></li><li><span class="workflow-number">02</span><span><strong>Connect every suggestion</strong><p>See the source passages that support the proposed code.</p></span></li><li><span class="workflow-number">03</span><span><strong>Make a clear decision</strong><p>Review the evidence and resolve gaps before approval.</p></span></li></ol><div class="story-bottom">${icon('link')}Evidence beside the decision. Always.</div></aside></div>
  <div class="section-heading"><h2>Recent documents</h2><a href="#documents">View all ${icon('arrow')}</a></div><div class="document-list" id="documentsTable">${LIST_HEADER}<p class="empty-state">Loading documents…</p></div></section>`;
}

function documentsView(name) {
  const queue = name === 'queue';
  return `<section class="view-entrance"><div class="heading-row documents-heading"><div><span class="eyebrow">${queue ? 'A PLACE FOR THE OPEN QUESTIONS' : 'THE ORIGINAL, ALWAYS IN VIEW'}</span><h1>${queue ? 'Review queue.' : 'Your documents.'}</h1><p>${queue ? 'Keep missing information visible, so uncertainty becomes a clear next step.' : 'Keep source notes, supporting evidence and coding decisions together.'}</p></div><div class="heading-actions"><button type="button" class="button primary" data-action="upload">${icon('plus')}New document</button></div></div><p class="section-description" id="listDescription">Loading…</p>${queue ? '' : `<label class="search-field">${icon('search')}<input id="documentSearch" aria-label="Search documents" placeholder="Search documents…" autocomplete="off"></label><div style="height:18px"></div>`}<div class="document-list" id="documentsTable">${LIST_HEADER}<p class="empty-state">Loading documents…</p></div><p class="checks-disclaimer">${queue ? 'Documents waiting for a clarification, a review decision or a provider reconciliation.' : 'Synthetic documents only. Each review decision is tied to the revision it was made on.'}</p></section>`;
}

function howItWorksView() {
  const mode = lookup({ live: 'Provider mode in this deployment: live requests to the configured provider.', replay: 'Provider mode in this deployment: REPLAY — recorded responses, not live output.', disabled: 'Provider mode in this deployment: disabled — no proposals are requested.' }, state.session?.provider_mode, '');
  return `<section class="view-entrance"><div class="heading-row how-heading"><div><span class="eyebrow">A FOCUSED PRODUCT, BY DESIGN</span><h1>A reason behind<br><em>every suggestion.</em></h1><p>A standalone CPT workspace that keeps the original clinical story and the coding review connected.</p></div><button type="button" class="button primary" data-action="upload">Start a coding review ${icon('arrow')}</button></div><div class="flow-overview"><article class="flow-card"><span class="step">01</span><h2>The source<br>comes first.</h2><p>Upload the original PDF or Word document, or paste the note. The text is extracted as written; scanned pages are read with OCR where it is available, and anything that could not be read is listed.</p></article><article class="flow-card"><span class="step">02</span><h2>Suggestions<br>need support.</h2><p>A coding provider proposes CPT codes. A code is kept only with exact source passages, then checked separately against the connected reference files for the service date. Whatever cannot be checked is labelled not verified.</p></article><article class="flow-card"><span class="step">03</span><h2>Review makes<br>the difference.</h2><p>Answer focused clarifications, approve or reject each code, confirm or reinstate each code a documentation check excluded, and download a draft or reviewed report. A changed source invalidates earlier decisions.</p></article></div><div class="how-note"><strong>This is a synthetic demonstration.</strong><br>Licensed CPT descriptors and NCCI procedure-to-procedure edits are not connected in this release, so descriptors are withheld and code-set validity and PTP edits stay not verified. The documentation checks read declared wording, layouts and check boxes, and they can miss wording they do not recognise, so every code needs a reviewer who reads the whole document. Accuracy has not been independently evaluated; no accuracy percentage or payment guarantee is claimed.${mode ? `<br>${escapeHtml(mode)}` : ''}</div><button type="button" class="button secondary" data-action="about">${icon('info')}About CPT Studio</button></section>`;
}

function messageView(title, detail, retry = false) {
  return `<section class="view-entrance"><a class="back-link" href="#documents">${icon('arrow')}All documents</a><div class="check-list-card"><p class="empty-state"><strong>${escapeHtml(title)}</strong><br>${escapeHtml(detail)}</p>${retry ? '<p class="empty-state"><button type="button" class="button secondary" data-action="retry">Try again</button></p>' : ''}</div></section>`;
}

function documentLayout(doc) {
  const spans = [];
  const codes = new Map();
  for (const proposal of proposalsIn(doc.assessment, 'selected')) {
    (proposal.evidence || []).forEach((evidence, index) => {
      const key = `${proposal.id}:${index}`;
      spans.push({ ...evidence, key });
      codes.set(key, proposal.code);
    });
    // Source passages CPT Studio selected because the provider's passages do not show the coded act.
    (proposal.support?.source || []).forEach((evidence, index) => {
      const key = `${proposal.id}:s${index}`;
      spans.push({ ...evidence, key });
      codes.set(key, proposal.code);
    });
  }
  const layout = layoutDocument(doc.revision?.text || '', doc.revision?.pages, spans);
  return { pages: layout.pages, unlocated: new Set(layout.unlocated), codes };
}

function renderPieces(pieces, layout) {
  return pieces.map(piece => {
    if (!piece.keys) return escapeHtml(piece.text);
    const codes = [...new Set(piece.keys.map(key => layout.codes.get(key)))].join(', ');
    return `<button type="button" class="evidence-mark" data-evidence="${escapeHtml(piece.keys[0])}" data-keys="${escapeHtml(piece.keys.join(' '))}" title="${escapeHtml(`Evidence for ${codes}`)}">${escapeHtml(piece.text)}</button>`;
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
  const metadata = [['SERVICE DATE', factValue(facts.service_date, null, true)], ['SETTING', factValue(facts.setting, SETTING_LABELS)], ['PATIENT STATUS', factValue(facts.patient_status, PATIENT_LABELS)], ['BILLING CONTEXT', factValue(facts.billing_context, BILLING_LABELS)]]
    .map(([label, value]) => `<span><b>${label}</b>${escapeHtml(value)}</span>`).join('');
  const header = `<span class="paper-eyebrow">${escapeHtml(`${state.session?.workspace?.name || 'CPT Studio'} · synthetic document`.toUpperCase())}</span><h3>${escapeHtml(sourceName(revision))}</h3><p class="paper-subtitle">${escapeHtml(subtitle)}</p><div class="paper-metadata">${metadata}</div>`;
  const emptyText = extraction.status === 'failed' ? 'No text could be extracted from this document.' : 'The document text will appear here once extraction finishes.';
  const papers = layout.pages.map((page, index) => {
    const body = page.paragraphs.map(pieces => `<p class="source-text">${renderPieces(pieces, layout)}</p>`).join('');
    return `<article class="source-paper" data-page="${escapeHtml(page.page)}" aria-label="${escapeHtml(`Page ${page.page}`)}">${index === 0 ? header : ''}${body || (index === 0 && !hasText ? `<p class="card-empty">${emptyText}</p>` : '')}<div class="paper-footer"><span>SYNTHETIC DOCUMENT · NOT FOR BILLING</span><span>${hasText ? escapeHtml(`${pad(page.page)} / ${pad(total)}`) : ''}</span></div></article>`;
  }).join('');
  const pageLabel = hasText ? `Page ${layout.pages[0].page} of ${total}` : 'No text extracted';
  const original = revision.source_file ? `<a href="/api/encounters/${escapeHtml(encodeURIComponent(doc.id))}/original" download>${icon('download')}Download original</a>` : '';
  return `<section class="source-panel" aria-label="Source document"><div class="source-toolbar">${icon('file')}<h2>Original document</h2><span class="page-number" id="pageNumber" data-total="${escapeHtml(total)}">${escapeHtml(pageLabel)}</span></div><div class="source-paper-wrap" id="sourceScroll">${notes.map(note => `<div class="reference-note">${icon('info')}<span>${escapeHtml(note)}</span></div>`).join('')}${papers}</div><div class="source-bottom"><span></span>Original text as extracted${original}</div></section>`;
}

function reviewMeta(doc) {
  const facts = doc.context?.facts || {};
  const items = [metaFact(facts.service_date, null, 'Service date', true), metaFact(facts.setting, SETTING_LABELS, 'Setting'), categoryName(), doc.revision?.number ? `Revision ${doc.revision.number}` : ''];
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

function referenceNote(proposal) {
  const checks = Array.isArray(proposal.checks) ? proposal.checks : [];
  const lines = [];
  if (proposal.status === 'excluded' && proposal.exclusion_reason) lines.push(`Excluded: ${proposal.exclusion_reason}`);
  if (proposal.supported === false) lines.push(`${proposal.family_label || 'This service'} is not covered by a profiled GI service family in this release — review required.`);
  for (const check of checks) if (check.status === 'fail' || check.status === 'warn') lines.push(`${lookup(CHECK_LABELS, check.status, '')} · ${check.label}: ${check.detail}`);
  const notVerified = checks.filter(check => check.status === 'not_verified').map(check => check.label);
  if (notVerified.length) lines.push(`Not verified: ${notVerified.join('; ')}.`);
  return lines.length ? `<div class="reference-note">${icon('info')}<span>${lines.map(escapeHtml).join('<br>')}</span></div>` : '';
}

function modifierNote(proposal) {
  const items = Array.isArray(proposal.modifier_considerations) ? proposal.modifier_considerations : [];
  return items.length ? `<div class="reference-note">${icon('info')}<span>${escapeHtml(`Modifier considerations, never assigned automatically: ${items.join(' ')}`)}</span></div>` : '';
}

function evidenceChips(proposal, layout) {
  const unrelated = new Set(Array.isArray(proposal.support?.unrelated) ? proposal.support.unrelated : []);
  const provider = (proposal.evidence || []).map((evidence, index) => {
    const key = `${proposal.id}:${index}`;
    if (layout.unlocated.has(key)) return `<span class="evidence-chip unlocated">${icon('info')}<span>${escapeHtml(`“${evidence?.text ?? ''}” — not found at this position in the current revision, so it is not highlighted.`)}</span></span>`;
    const note = unrelated.has(index) ? ' — cited by the provider; does not show the coded act' : '';
    return `<button type="button" class="evidence-chip" data-evidence="${escapeHtml(key)}">${icon('link')}<span>${escapeHtml(`“${evidence.text}”${note}`)}</span></button>`;
  });
  const source = (proposal.support?.source || []).map((evidence, index) => {
    const key = `${proposal.id}:s${index}`;
    if (layout.unlocated.has(key)) return '';
    return `<button type="button" class="evidence-chip" data-evidence="${escapeHtml(key)}">${icon('link')}<span>${escapeHtml(`“${evidence.text}” — selected from the source by CPT Studio`)}</span></button>`;
  });
  const sourceLabel = source.some(Boolean) ? groupLabel('Source passages that show the coded act') : '';
  return provider.join('') + sourceLabel + source.join('');
}

function clarificationQuestion(clarification, doc) {
  const answer = canEdit(doc) ? `<br><button type="button" class="button secondary" data-action="addendum" data-clarification="${escapeHtml(clarification.id)}">Answer with an addendum</button>` : '';
  return `<div class="clarification-question"><strong>Clarification needed</strong><br>${escapeHtml(clarification.question)}${clarification.reason ? `<span class="clarification-reason">${escapeHtml(clarification.reason)}</span>` : ''}${answer}</div>`;
}

function codeCard(proposal, doc, layout) {
  const count = (proposal.evidence || []).length;
  const units = Number.isInteger(proposal.units) && proposal.units > 1 ? `Units: ${proposal.units} · ` : '';
  const second = proposal.support?.origin === 'second_review' ? `<span class="small-badge">Second review</span>` : '';
  return `<article class="code-card" id="card-${escapeHtml(proposal.id)}" tabindex="-1"><div class="code-card-main"><div class="code-card-top"><span class="code-category">${escapeHtml(proposal.eyebrow || proposal.family_label || '')}</span>${second}${proposalBadge(proposal)}</div><strong class="code-number">${escapeHtml(proposal.code)}</strong><h3>Description withheld</h3><span class="code-short-note">${escapeHtml(units + (proposal.descriptor?.label || 'No licensed CPT descriptor is connected.'))}</span>${proposal.rationale ? `<p class="code-rationale">${escapeHtml(proposal.rationale)}</p>` : ''}${clarificationsFor(proposal, doc).map(item => clarificationQuestion(item, doc)).join('')}</div><div class="evidence-section"><div class="evidence-label">${icon('link')}${escapeHtml(passagesLabel(count))}</div>${evidenceChips(proposal, layout)}${referenceNote(proposal)}${modifierNote(proposal)}</div>${decisionLine(proposal)}${cardActions(proposal)}</article>`;
}

function clarificationCard(clarification, doc) {
  const family = clarification.family ? familyLabel(doc, clarification.family) : '';
  const answer = canEdit(doc) ? `<button type="button" class="button primary" data-action="addendum" data-clarification="${escapeHtml(clarification.id)}">Answer with an addendum ${icon('arrow')}</button>` : '';
  return `<div class="clarification-card"><span class="clarification-icon">${icon('help')}</span><h3>A question is better<br>than an assumption.</h3>${clarification.reason ? `<p>${escapeHtml(clarification.reason)}</p>` : ''}<div class="clarification-question"><strong>${escapeHtml(family ? `Clarification needed · ${family}` : 'Clarification needed')}</strong><br>${escapeHtml(clarification.question)}</div>${answer}</div>`;
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

function candidateSection(title, proposals, fallback, doc) {
  if (!proposals.length) return '';
  const items = proposals.map(proposal => {
    const allowed = Array.isArray(proposal.allowed_actions) ? proposal.allowed_actions : [];
    // Every action the server allows, in the card order: a reinstated code is approved or rejected here too.
    const decisions = ACTION_BUTTONS.filter(([name]) => allowed.includes(name)).map(([name]) => decisionButton(name, proposal));
    // A reinstated code whose gate withholds approve is told to add the missing documentation, so the row offers the
    // addendum itself; POST /addenda needs no clarification (round 6, bypass:1).
    const withheld = proposal.decision_state === 'reinstated' && typeof proposal.approve_withheld_by === 'string' && proposal.approve_withheld_by;
    const addendum = withheld && doc && canEdit(doc) ? ['<button type="button" class="button secondary" data-action="addendum">Add the missing documentation (addendum)</button>'] : [];
    const actions = decisions.concat(addendum).join(' ');
    return checkItem('muted', 'info', `${proposal.code} · ${proposal.family_label || proposal.family || ''}`, [proposal.exclusion_reason || fallback, candidateDecision(proposal)].filter(Boolean).join(' '), actions);
  });
  return `${sectionHeading(title, proposals.length)}<div class="check-list-card">${items.join('')}</div>`;
}

const SERVICE_STATUS_LABELS = { performed: 'performed', incomplete: 'performed, incomplete', planned: 'planned', historical: 'historical', cancelled: 'cancelled', negated: 'documented as not performed', uncertain: 'not established' };
const CODING_TONES = { incomplete: 'pending', pending_review: '', reviewed: '', not_established: 'muted' };

// The encounter's coding completeness, kept apart from whether a proposal is ready for review.
function codingBanner(doc) {
  const coding = doc.coding;
  if (!coding || !coding.statement) return '';
  const title = lookup({ incomplete: 'Coding for this encounter is incomplete', pending_review: 'Every documented service has a proposal to review', reviewed: 'Every documented service has a reviewed decision', not_established: 'Coding completeness not established' }, coding.state, 'Coding completeness');
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
    if (done && service.included_in) lines.push(`Included in ${service.included_in}: that service's code includes this examination, so no code of its own is asked.`);
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
  return `${sectionHeading('Documented services', services.length)}<div class="check-list-card">${items.join('')}${secondReviewItem(doc)}</div>`;
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

function emptySelectionCopy(assessment) {
  // Codes a documentation check excluded still need a reviewer decision, so the panel never says nothing was
  // proposed while they wait below (round 5, bypass:6). Only the codes still waiting are counted, as readiness
  // counts them, so a decided set is never told it needs a decision (round 6, bypass:4).
  const excluded = proposalsIn(assessment, 'excluded');
  const reinstatable = excluded.filter(proposal => proposal.reinstatable);
  const waiting = reinstatable.filter(proposal => proposal.decision_state === 'undecided' || proposal.decision_state === 'reinstated').length;
  if (waiting === 1) return 'One code that a documentation check excluded needs a reviewer\'s decision under Excluded candidates below.';
  if (waiting) return `${waiting} codes that a documentation check excluded need a reviewer's decision under Excluded candidates below.`;
  if (reinstatable.length) return 'Every code that a documentation check excluded has a decision; see Excluded candidates below.';
  if (excluded.length || proposalsIn(assessment, 'alternative').length) return 'No code is selected for approval. The provider proposed only codes that were excluded or offered as alternatives; they are listed below.';
  // A provider check that failed (a response refused whole, or no usable result) says why there are no proposals;
  // "none were proposed" would misstate a response that was never read (round 7, bypass:1).
  const provider = (Array.isArray(assessment.encounter_checks) ? assessment.encounter_checks : []).find(check => check && check.id === 'provider.status');
  if (provider && provider.status === 'fail' && typeof provider.detail === 'string' && provider.detail) return provider.detail;
  return 'No CPT codes were proposed for this document.';
}

function suggestionsPanel(doc, layout) {
  const assessment = doc.assessment;
  const selected = proposalsIn(assessment, 'selected');
  const inline = new Set(selected.flatMap(proposal => clarificationsFor(proposal, doc).map(item => item.id)));
  const general = openClarifications(doc).filter(item => !inline.has(item.id)).map(item => clarificationCard(item, doc));
  const cards = selected.length ? selected.map(proposal => codeCard(proposal, doc, layout)) : [`<div class="check-list-card"><p class="card-empty">${escapeHtml(emptySelectionCopy(assessment))}</p></div>`];
  return `<div class="card-stack">${codingBanner(doc)}${general.join('')}${cards.join('')}</div>${documentedServices(doc)}${unsupportedSection(assessment)}${candidateSection('Alternatives (never selectable)', proposalsIn(assessment, 'alternative'), 'Offered by the provider as an alternative and not selected. Alternatives cannot be approved.', doc)}${candidateSection('Excluded candidates', proposalsIn(assessment, 'excluded'), 'Excluded from CPT-only results.', doc)}<div class="review-insight">${icon('shield')}<div><strong>The source remains the starting point</strong><p>The checks hold or exclude planned, historical, cancelled and uncertain services when they recognise the wording, and they can miss wording they do not recognise. Read the document before deciding; agreement between sources is not treated as verification.</p></div></div>`;
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
  return `<div class="card-stack"><div class="check-list-card">${groupLabel('Encounter')}${checkItems(assessment.encounter_checks)}</div>${perCode}<div class="check-list-card">${groupLabel('Reference sources')}${referenceItems(assessment.reference_sources)}</div></div><p class="checks-disclaimer">Checks come from the connected reference files and this service's own documentation rules. Anything they do not cover is shown as not verified, and agreement between sources is not treated as verification.</p>`;
}

function timelineEntry(title, lines, struck = false) {
  return `<div class="timeline-entry"><span class="timeline-dot"></span><div><strong>${struck ? `<s>${escapeHtml(title)}</s>` : escapeHtml(title)}</strong>${lines.filter(Boolean).map(line => `<p>${escapeHtml(line)}</p>`).join('')}</div></div>`;
}

function usageText(run) {
  const credits = run.usage?.creditsConsumed;
  if (typeof credits !== 'number') return 'Usage not reported';
  return run.usage_basis === 'provider_reported_credits_not_usd' ? `${credits} provider-reported credits (not USD)` : `${credits} credits (basis: ${run.usage_basis || 'not recorded'})`;
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
  const runEntries = runs.map(run => timelineEntry(
    [lookup({ corti: 'Corti', replay: 'Replay' }, run.provider, run.provider || 'Provider'), lookup({ live: 'live', replay: 'REPLAY — recorded response, not live output' }, run.mode, run.mode || 'mode not recorded'), run.purpose === 'second_review' ? 'Second review' : '', lookup(RUN_STATES, run.state, run.state || 'state not recorded')].filter(Boolean).join(' · '),
    [[run.http_status ? `HTTP ${run.http_status}` : 'No HTTP response recorded', typeof run.latency_ms === 'number' ? `${(run.latency_ms / 1000).toFixed(1)} s` : '', usageText(run)].filter(Boolean).join(' · '),
      run.purpose === 'second_review' && Array.isArray(run.scope_items) && run.scope_items.length ? `Asked about: ${run.scope_items.join('; ')}.` : '',
      run.reused_from ? 'Reused the stored response of an identical earlier request; no new provider call was made.' : '',
      run.reconciled ? 'Unknown outcome reconciled by a member.' : '', run.error ? `Error: ${run.error}` : '', formatTimestamp(run.created_at)]));
  const eventEntries = events.map(event => timelineEntry(event.summary || event.event || 'Event', [[event.actor || 'System', formatTimestamp(event.created_at)].filter(Boolean).join(' · ')]));
  const card = (label, entries, empty) => `<div class="timeline-card">${groupLabel(label)}${entries.length ? entries.join('') : `<p class="card-empty">${empty}</p>`}</div>`;
  return `<div class="card-stack">${card('Decisions', decisions, 'No decisions recorded yet.')}${card('Provider runs', runEntries, 'No provider request has been made for this document.')}${card('Activity', eventEntries, 'No activity recorded.')}</div>`;
}

// Each row shows the LATEST job of its stage (a context change, a resume or a second review runs a stage again: the
// first one's "Done" was shown while the new one waited), and the second review's row appears once one was asked for.
function progressCard(doc) {
  const stages = Array.isArray(doc.pipeline?.stages) ? doc.pipeline.stages : [];
  const rows = stages.some(item => item?.kind === 'review2') ? [...STAGES, SECOND_REVIEW_STAGE] : STAGES;
  const items = rows.map(([kind, label]) => {
    const stage = [...stages].reverse().find(item => item?.kind === kind);
    if (!stage) return checkItem('muted', 'clock', label, 'Not started');
    const [tone, iconName] = lookup(STAGE_LOOKS, stage.state, ['pending', 'info']);
    return checkItem(tone, iconName, label, `${lookup(STAGE_STATES, stage.state, stage.state || 'Unknown')}${stage.error ? ` — ${stage.error}` : ''}`);
  }).join('');
  const stop = doc.pipeline?.can_stop && doc.permissions?.can_review ? `<div class="progress-actions"><button type="button" class="button secondary" data-action="stop">${icon('stop')}Stop</button><p>Stop cancels queued stages and prevents an unsent provider request.</p></div>` : '';
  return `<div class="check-list-card progress-card" aria-live="polite"><div class="panel-heading">${icon('clock')}<h2>Processing this document</h2><span class="small-badge">Updates automatically</span></div>${items}${stop}</div>`;
}

function infoCard(titleHtml, lines, actions = '') {
  return `<div class="clarification-card"><span class="clarification-icon">${icon('info')}</span><h3>${titleHtml}</h3>${lines.filter(Boolean).map(line => `<p>${escapeHtml(line)}</p>`).join('')}${actions}</div>`;
}

function reconcileCard(doc) {
  const run = (doc.provider_runs || []).filter(item => item.state === 'unknown' && !item.reconciled).pop();
  const canReview = doc.permissions?.can_review;
  const detail = run ? `<div class="clarification-question"><strong>Unreconciled request</strong><br>${escapeHtml([run.purpose === 'second_review' ? 'Second review' : '', formatTimestamp(run.created_at), run.error].filter(Boolean).join(' · ') || 'No further detail was recorded.')}</div>` : '';
  const form = run && canReview ? `<form id="reconcileForm" data-run="${escapeHtml(run.id)}" novalidate><label class="field-label">Reconciliation note<textarea id="reconcileNote" rows="3" maxlength="2000" placeholder="What is known about this request…"></textarea></label><p class="form-error" id="reconcileError" role="alert" hidden></p><button type="submit" class="button primary">Record reconciliation ${icon('check')}</button></form>` : '';
  const viewer = run && !canReview ? '<p class="checks-disclaimer">Only owners and reviewers can record a reconciliation.</p>' : '';
  return `<div class="clarification-card"><span class="clarification-icon">${icon('help')}</span><h3>The provider outcome<br>is unknown.</h3><p>A request was sent but no response was recorded. Nothing is resent automatically: record what is known before one new attempt is allowed.</p>${detail}${form}${viewer}</div>`;
}

function stateCards(doc) {
  const cards = [];
  if (doc.pipeline?.busy) cards.push(progressCard(doc));
  const runs = doc.provider_runs || [];
  const stages = doc.pipeline?.stages || [];
  // Any unreconciled unknown outcome, the second review's included: nothing is sent again until it is reconciled.
  if (doc.state === 'provider_unknown' || runs.some(run => run.state === 'unknown' && !run.reconciled)) cards.push(reconcileCard(doc));
  if (doc.state === 'extraction_failed') {
    cards.push(infoCard('The text could not<br>be read.', ['No CPT proposals were requested because no text could be extracted; the reasons are listed above the document. Upload another copy, or paste the text instead.'], `<button type="button" class="button primary" data-action="upload">${icon('plus')}New document</button>`));
  }
  if (doc.state === 'provider_failed') {
    const failed = runs.filter(run => run.state === 'failed').pop();
    cards.push(infoCard('The provider request<br>failed.', [failed?.error ? `Error: ${failed.error}` : 'The provider did not return proposals.', 'Nothing was resent automatically, and any recorded usage is kept.']));
  }
  if (doc.state === 'provider_not_run') {
    const predict = stages.find(stage => stage.kind === 'predict');
    cards.push(infoCard('No proposals were<br>requested.', [predict?.error || (state.session?.provider_mode === 'disabled' ? 'Provider requests are disabled in this deployment.' : 'The provider step did not run for this revision.')]));
  }
  if (doc.state === 'stopped') {
    const resume = doc.pipeline?.can_resume ? `<button type="button" class="button primary" data-action="resume">${icon('arrow')}Resume processing</button>` : '';
    // A stage the system cancelled (it expired in the queue, or a worker stopped mid-stage) is not a member's Stop:
    // say what was recorded instead of telling the member they stopped it.
    const cause = [...stages].reverse().find(stage => stage.state === 'cancelled' && stage.error);
    if (doc.pipeline?.stopped_by_member === false && cause) {
      const label = lookup(Object.fromEntries(STAGES), cause.kind, 'A processing stage');
      cards.push(infoCard('Processing did<br>not finish.', [`${label}: ${cause.error}`, 'Nothing was resent automatically.'], resume));
    } else {
      cards.push(infoCard('Processing was<br>stopped.', ['Queued stages were cancelled, and no unsent provider request is made unless processing is resumed.'], resume));
    }
  }
  return cards.join('');
}

function tabContent(doc, tab, layout) {
  if (tab === 'checks') return checksPanel(doc);
  if (tab === 'timeline') return activityPanel(doc);
  return suggestionsPanel(doc, layout);
}

function reviewView(doc, layout, tab, entrance) {
  const selected = proposalsIn(doc.assessment, 'selected');
  const tabs = doc.assessment ? `<div class="result-tabs" role="tablist" aria-label="Review details">${TABS.map(([id, label]) => `<button type="button" role="tab" id="tab-${id}" data-tab="${id}" aria-controls="resultContent" aria-selected="${tab === id}" tabindex="${tab === id ? 0 : -1}">${label}${id === 'codes' ? ` <span class="tab-count">${selected.length}</span>` : ''}</button>`).join('')}</div><div id="resultContent" role="tabpanel" tabindex="0" aria-labelledby="tab-${tab}">${tabContent(doc, tab, layout)}</div>` : '';
  const exportButton = doc.assessment ? `<button type="button" class="button primary" data-action="export">${icon('download')}Export</button>` : '';
  return `<section${entrance ? ' class="view-entrance"' : ''}><a class="back-link" href="#documents">${icon('arrow')}All documents</a><div class="heading-row review-heading"><div><span class="eyebrow">CPT REVIEW · SYNTHETIC</span><h1>${escapeHtml(doc.title || 'Untitled document')}</h1><div class="review-meta">${reviewMeta(doc)}</div></div><div class="heading-actions"><button type="button" class="button secondary" data-action="upload">${icon('plus')}New document</button>${exportButton}</div></div><div class="review-layout">${sourcePanel(doc, layout)}<section class="review-column" aria-label="Coding review"><div class="results-topline"><h2>Coding review</h2><span class="small-badge">CPT only</span></div>${stateCards(doc)}${tabs}</section></div><div class="sample-strip"><span>SYNTHETIC DEMONSTRATION · Not clinical approval, coding advice or billing.</span><a href="#how-it-works">About the workflow ${icon('arrow')}</a></div></section>`;
}

function exportOption(kind, fmt, title, detail) {
  return `<button type="button" class="export-option" data-export-kind="${kind}" data-export-fmt="${fmt}"><span class="export-format">${fmt.toUpperCase()}</span><span><strong>${title}</strong><small>${detail}</small></span>${icon('download')}</button>`;
}

function exportOptions(readiness) {
  const draft = readiness.draft === true ? `<div class="export-group">${groupLabel('Draft — not reviewed')}${exportOption('draft', 'txt', 'Coding report (TXT)', 'Codes, evidence, checks and open questions')}${exportOption('draft', 'csv', 'Structured CSV', 'One row per code with its review state')}</div>` : '';
  const reviewed = readiness.reviewed === true ? `<div class="export-group">${groupLabel('Reviewed')}${exportOption('reviewed', 'txt', 'Coding report (TXT)', 'Approved selections, rejections and reviewers')}${exportOption('reviewed', 'csv', 'Structured CSV', 'One row per item, with decisions')}</div>` : '';
  return draft + reviewed;
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
  location.assign(`/login/?next=${encodeURIComponent(`/${location.hash}`)}`);
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
    ({ encounters } = await api('/api/encounters'));
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

async function loadDocument(id, token, silent) {
  clearTimeout(state.poll.timer);
  let doc;
  try {
    doc = await api(`/api/encounters/${encodeURIComponent(id)}`);
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
  if (!doc.assessment) state.currentTab = 'codes';
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
  if (!TABS.some(([id]) => id === tab) || !state.doc?.assessment || !$('#resultContent')) return;
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
    const created = await api('/api/encounters', { method: 'POST', form });
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
      await api(`/api/encounters/${encodeURIComponent(state.doc.id)}/context`, { method: 'POST', json: body });
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
      await api(`/api/encounters/${encodeURIComponent(state.doc.id)}/addenda`, { method: 'POST', json: { text, clarification_id: state.addendum.clarificationId, synthetic_attestation: 'yes' } });
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
      await api(`/api/encounters/${encodeURIComponent(state.doc.id)}/stop`, { method: 'POST', json: {} });
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
      await api(`/api/encounters/${encodeURIComponent(state.doc.id)}/resume`, { method: 'POST', json: {} });
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
      await api(`/api/encounters/${encodeURIComponent(state.doc.id)}/second-review`, { method: 'POST', json: {} });
      await afterChange('Second review requested.');
    } catch (error) {
      toast(error.message);
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
      await api(`/api/encounters/${encodeURIComponent(state.doc.id)}/reconcile`, { method: 'POST', json: { provider_run_id: form.dataset.run, note } });
      await afterChange('Reconciliation recorded.');
    } catch (error) {
      showError('reconcileError', error.message);
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
      const report = await api(`/api/encounters/${encodeURIComponent(state.doc.id)}/reports`, { method: 'POST', json: { kind, fmt } });
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
    retry: route,
  })[action.dataset.action]?.();
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
  document.addEventListener('keydown', onKeydown);
  document.addEventListener('input', event => { if (event.target.id === 'documentSearch') applySearch(); });
  document.addEventListener('submit', event => {
    if (event.target.id !== 'reconcileForm') return;
    event.preventDefault();
    submitReconcile(event.target);
  });
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
    factValue, metaFact, exportStatusText, documentLayout, reviewView, documentRow, listBody, listDescription,
    inviteMarkup, overviewView, documentsView, howItWorksView, exportOptions, state, QUEUE_STATES, decisionLine,
    hasAgentDecision, candidateDecision, ACKNOWLEDGEMENTS, emptySelectionCopy, attestationText,
    codingBanner, documentedServices, evidenceChips,
  };
}
if (typeof document !== 'undefined') boot();
