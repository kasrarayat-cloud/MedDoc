#!/usr/bin/env node
'use strict';
/*
 * Browser verification of a running CPT Studio (the deployed site or a local one)
 * with the synthetic documents from ops/verification.
 *
 *   node ops/verify_browser.cjs --base-url https://cpt.quillmd.com --credentials agent.json \
 *     --docs OUT_FROM_GENERATE --manifest ops/verification/manifest.json --out EVIDENCE_DIR \
 *     [--only gi-01,gi-03] [--deadline-seconds 300] [--stop-on-failure] [--allow-live-provider]
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
 * (or stops with --stop-on-failure). Everything is written to EVIDENCE_DIR/evidence.json,
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
const VIEWPORTS = { desktop: { width: 1440, height: 1000 }, mobile: { width: 390, height: 844 } };
const UI_TIMEOUT_MS = 30000;
const POLL_MS = 2000;
const MAX_POLL_ERRORS = 3;
const INCOMPLETE_SIGNAL = /incomplete|discontinu|reduced|\b5[23]\b/i;
const AGENT_LABEL = 'agent-executed synthetic review';
const USAGE = 'usage: verify_browser.cjs --base-url URL --credentials FILE --docs DIR --manifest FILE --out DIR '
  + '[--only IDS] [--deadline-seconds N] [--stop-on-failure] [--allow-live-provider]';

// --- small pure helpers ----------------------------------------------------------------

class UsageError extends Error {}

function parseArgs(argv) {
  const flags = new Set(['stop-on-failure', 'allow-live-provider']);
  const values = new Set(['base-url', 'credentials', 'docs', 'manifest', 'out', 'only', 'deadline-seconds']);
  const opts = { only: null, deadlineSeconds: 300, stopOnFailure: false, allowLiveProvider: false };
  for (let i = 0; i < argv.length; i += 1) {
    const [name, inline] = argv[i].replace(/^--/, '').split(/=(.*)/s);
    if (!argv[i].startsWith('--')) throw new UsageError(`unexpected argument ${argv[i]}`);
    if (flags.has(name)) {
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
    out.push(check('revision.source', 'hard', rev.kind === 'paste' && !rev.source_file, `kind ${rev.kind}, source_file ${JSON.stringify(rev.source_file)}`));
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

function planDecisions(enc, reviewPlan, notes) {
  const ready = proposalsOf(enc).filter(p => p.bucket === 'selected' && p.status === 'ready' && p.decision_state === 'undecided'
    && (p.allowed_actions || []).includes('approve'));
  const rule = reviewPlan?.reject;
  let designated = null;
  if (rule) {
    const family = ready.filter(p => p.family === rule.family && (p.allowed_actions || []).includes('reject'));
    designated = family.find(p => (rule.prefer_codes || []).includes(p.code)) || family[family.length - 1] || null;
  }
  const decisions = ready.map(p => ({
    proposal_id: p.id, code: p.code, family: p.family, action: p === designated ? 'reject' : 'approve',
    designated: p === designated, note: p === designated ? notes.reject : notes.approve,
  }));
  return { decisions, designated_missing: Boolean(rule) && !designated };
}

function checkReadiness(enc) {
  const active = proposalsOf(enc).filter(p => p.bucket === 'selected' && !isExcluded(p));
  const decided = active.every(p => DECIDED.has(p.decision_state));
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
    const want = d.action === 'approve' ? 'approved' : 'rejected';
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

function checkDecisionDom(decisions, enc, cards) {
  return decisions.filter(d => d.http_status === 201).map(d => {
    const card = cards.find(c => c.id === `card-${d.proposal_id}`);
    const reviewer = proposalsOf(enc).find(p => p.id === d.proposal_id)?.decision?.reviewer || '';
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
    provider_runs: (enc.provider_runs || []).map(r => ({ provider: r.provider, mode: r.mode, state: r.state, http_status: r.http_status, usage: r.usage, usage_basis: r.usage_basis, reused_from: r.reused_from, latency_ms: r.latency_ms })),
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
  const documents = manifest.documents.filter(d => !opts.only || opts.only.includes(d.id)).map(doc => {
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
  return { marks, cards };
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
    const badge = document.querySelector(`[id="card-${id}"] .code-card-top .status`);
    const text = badge ? badge.textContent.trim() : '';
    return action === 'approve' ? /^Approved/.test(text) : text === 'Rejected';
  }, [decision.proposal_id, decision.action], { timeout: UI_TIMEOUT_MS }).then(() => true, () => false);
  return { ...record, ui_updated: shown };
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
    const id = await uploadDocument(page, opts.baseUrl, item, record.timings);
    record.encounter_id = id;
    await page.waitForURL(url => new URL(url).hash === `#doc/${id}`, { timeout: UI_TIMEOUT_MS });
    record.review_url = page.url();
    const { enc, timedOut } = await waitForProcessing(page, opts.baseUrl, id, started + opts.deadlineSeconds * 1000, record.state_history);
    record.timings.processing_done_at = isoNow();
    record.timings.processing_seconds = (Date.parse(record.timings.processing_done_at) - Date.parse(record.timings.encounter_created_at)) / 1000;
    saveSnapshot(record, docDir, opts.out, 'after_processing', enc);
    if (timedOut) throw new Error(`processing did not finish within ${opts.deadlineSeconds}s (state ${enc.state}); no Stop was issued and nothing is retried`);
    add(checkPipeline(enc));
    add(checkExtraction(doc.expected_extraction || {}, enc, item.delivery, item.sourceText));
    add(checkContext(doc.expected_context, enc));
    add(checkRouting(doc.expected_routing || {}, enc));
    add(checkEvidenceExact(enc));
    add(checkMustNotCode(doc.must_not_code, enc));
    add(checkClarifications(doc.expected_clarifications, enc));
    add(checkIncomplete(doc.incomplete_services, enc));
    add([await checkOriginal(page, opts.baseUrl, id, item.delivery)]);
    await waitForReviewScreen(page).catch(async () => {
      add([check('ui.refreshed_itself', 'soft', false, 'the review did not leave the processing view on its own within 30 s; reloaded')]);
      await page.reload({ waitUntil: 'domcontentloaded' });
      await waitForReviewScreen(page);
    });
    const before = await readDom(page);
    add(checkEvidenceMarks(enc, before.marks, before.cards));

    const plan = planDecisions(enc, doc.review_plan, manifest.review_notes);
    record.designated_rejection = plan.decisions.find(d => d.designated)?.code || null;
    if (plan.designated_missing) add([check('decisions.designated_rejection', 'soft', false, `no ready selected proposal in ${doc.review_plan.reject.family} to reject`)]);
    for (const decision of plan.decisions) record.decisions.push(await decide(page, id, decision));
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
    add(checkPersistence(record.decisions, enc, afterDecisions, reloaded));
    add(checkDecisionDom(record.decisions, reloaded, after.cards));
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
    options: { only: opts.only, deadline_seconds: opts.deadlineSeconds, stop_on_failure: opts.stopOnFailure, allow_live_provider: opts.allowLiveProvider },
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

module.exports = {
  parseArgs, UsageError, cpSlice, safeName, sessionProblems, checkPipeline, checkExtraction, checkContext, checkRouting,
  checkEvidenceExact, checkMustNotCode, checkClarifications, checkIncomplete, planDecisions, checkReadiness,
  checkPersistence, checkEvidenceMarks, checkDecisionDom, expectedDownloads, checkDownloads, checkListing, summarize,
  documentResult,
};

if (require.main === module) {
  main(process.argv.slice(2)).then(code => { process.exitCode = code; }, error => {
    process.stderr.write(`verify_browser: ${error && error.stack || error}\n`);
    process.exitCode = 1;
  });
}
