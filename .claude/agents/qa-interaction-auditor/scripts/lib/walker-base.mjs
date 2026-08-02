// ============================================================================
// walker-base.mjs — shared utilities for QA Interaction Auditor walkers
// ----------------------------------------------------------------------------
// Each per-page walker imports these helpers so the per-page file stays
// small (URL + selectors + assertions). The flagship sweep-visit-page.mjs
// predates this and stays self-contained — that's deliberate; full-walk
// walkers are big enough to warrant their own scaffolding.
// ============================================================================

import { chromium } from '/opt/meddoc-pro/node_modules/playwright/index.mjs';
import { execSync } from 'node:child_process';
import { readFileSync, existsSync, statSync, unlinkSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const TEST_EMAIL = process.env.QA_AUDITOR_EMAIL ?? 'qa-auditor@quillmd.test';

// ──────────────────────────────────────────────────────────────────────
// Target resolution — SAFE BY DEFAULT (full-app audit 2026-07-24).
// ----------------------------------------------------------------------
// These defaults used to be `https://app.quillmd.com` / the prod postgres
// container, so a single forgotten env var pointed the transactional-tier
// walkers (which click affordances and assert DB deltas) at PRODUCTION and
// real doctor data. That is the same failure mode `packages/db/src/db-guard.ts`
// exists to prevent on the seeder side — "there is intentionally no force
// flag" — and the walker fleet did not inherit the discipline.
//
// Now: the isolated QA stack is the default for BOTH the app and the DB, and
// pointing at production requires an explicit, deliberate opt-in.
// ──────────────────────────────────────────────────────────────────────
const PROD_APP_HOSTS = new Set(['app.quillmd.com', 'pro.quillmd.com', 'admin.quillmd.com']);
const ALLOW_PROD = process.env.QA_AUDITOR_ALLOW_PROD === 'i-know-this-hits-production';

const APP_BASE = process.env.QA_AUDITOR_APP_URL ?? 'http://localhost:9020';
// Marketing pages are public, server-rendered and write nothing, so reading
// production there is equivalent to a normal visitor load and stays default.
const MARKETING_BASE =
  process.env.QA_AUDITOR_MARKETING_URL ?? 'https://quillmd.com';

/** Fail closed when the app target is production and the operator has not
 *  explicitly opted in. Mirrors assertNonProdDatabase() for the HTTP side. */
function assertNonProdAppTarget() {
  let host;
  try {
    host = new URL(APP_BASE).hostname;
  } catch {
    throw new Error(`QA_AUDITOR_APP_URL is not a valid URL: ${APP_BASE}`);
  }
  if (PROD_APP_HOSTS.has(host) && !ALLOW_PROD) {
    throw new Error(
      `REFUSING TO RUN: QA_AUDITOR_APP_URL points at production (${host}). ` +
        `The transactional walkers click affordances and assert DB deltas. ` +
        `Point it at the QA stack (http://localhost:9020) or, if you really ` +
        `mean it, set QA_AUDITOR_ALLOW_PROD=i-know-this-hits-production.`
    );
  }
}
assertNonProdAppTarget();

/** Is the app target production? Decided once, from the same string the
 *  refusal above reads, so the two can never disagree. */
const APP_TARGET_IS_PROD = (() => {
  try {
    return PROD_APP_HOSTS.has(new URL(APP_BASE).hostname);
  } catch {
    return false;
  }
})();

// ──────────────────────────────────────────────────────────────────────
// Ingress access log — the container is DERIVED FROM THE TARGET, never
// hardcoded (Rounds item F, 2026-08-02).
// ----------------------------------------------------------------------
// `recentMutations()` used to run `docker logs meddoc-pro-caddy-1`
// unconditionally. The QA stack has no Caddy container at all — but
// PRODUCTION'S IS ALWAYS RUNNING ON THIS HOST, so the call did not fail
// and did not return empty: it returned production's POST/PATCH/PUT/
// DELETE traffic and fed it into the classifier for a click made on QA.
//
// That is the failure this project keeps meeting from a new angle: the
// probe answered, so nothing looked wrong, and the answer was about a
// different system entirely. An unrelated production write inside the
// 12-second window is enough to reclassify a QA click.
//
// Now: no container is scraped unless one is named, and the QA target
// names none. The other three write signals (row-level DB snapshot,
// audit-count delta, and Playwright's own non-GET waitForResponse) are
// per-target and carry the assertion. And "we did not look" is recorded
// distinctly from "we looked and saw nothing" — a zero whose provenance
// is unknown is exactly what this rule exists to stop.
// ──────────────────────────────────────────────────────────────────────
const INGRESS_LOG_CONTAINER =
  process.env.QA_AUDITOR_INGRESS_CONTAINER ??
  (APP_TARGET_IS_PROD ? 'meddoc-pro-caddy-1' : '');

let ingressLogUnavailableReason = INGRESS_LOG_CONTAINER
  ? null
  : 'no ingress log container for this target — QA has no Caddy, and ' +
    "production's log describes a different system";

/** Whether the ingress-log write signal was actually available this run.
 *  Walkers put this on their result so a reader can tell an observed
 *  zero from an unobservable one. */
export function ingressLogSource() {
  return {
    container: INGRESS_LOG_CONTAINER || null,
    available: Boolean(INGRESS_LOG_CONTAINER) && !ingressLogUnavailableReason,
    reason: ingressLogUnavailableReason,
  };
}

// DB target for the snapshot/diff helpers. Previously hardcoded to the prod
// container + prod database in three separate places, so the "zero DB writes"
// assertions read PRODUCTION state even when driving the QA app — comparing
// prod before/after a QA interaction, which can never be meaningful.
const DB_CONTAINER = process.env.QA_AUDITOR_DB_CONTAINER ?? 'meddoc-qa-postgres-1';
const DB_NAME = process.env.QA_AUDITOR_DB_NAME ?? 'meddoc_qa_test';
const DB_USER = process.env.QA_AUDITOR_DB_USER ?? 'meddoc';

if (DB_NAME === 'meddoc' && !ALLOW_PROD) {
  throw new Error(
    `REFUSING TO RUN: QA_AUDITOR_DB_NAME is the production database ("meddoc"). ` +
      `Set it to a qa/test-marked database, or set ` +
      `QA_AUDITOR_ALLOW_PROD=i-know-this-hits-production.`
  );
}

/** Session file lives in /tmp keyed by sweepRunId so a single
 *  sweep-all.mjs run shares one session across 28 walkers. The
 *  orchestrator generates the id; walkers read it from
 *  process.env.QA_SWEEP_RUN_ID. Single-walker invocations (without
 *  the env var) use the literal "single" id and may collide with
 *  another concurrent single-walker run — that's fine; the auto-
 *  invalidation path repairs it. */
const SESSION_TTL_MS = 30 * 60 * 1000;

function sessionPath(sweepRunId = process.env.QA_SWEEP_RUN_ID ?? 'single') {
  return resolve(tmpdir(), `qa-auditor-session-${sweepRunId}.json`);
}

/** Emit one NDJSON line per event so sweep-all.mjs can fold them into
 *  the unified report without re-parsing prose output.
 *
 *  Fail-closed hook (full-app audit 2026-07-24): every walker builds its own
 *  `walker-result` and none of them consulted the DB-probe outcome, so a
 *  walker whose assertions never ran still reported `ok: true`. Rather than
 *  patch eight walkers (and require every future one to remember), the single
 *  choke point every walker already goes through downgrades `ok` and attaches
 *  the probe-failure count. A probe that errored proves nothing. */
export function emit(obj) {
  let payload = obj;
  if (obj && obj.event === 'walker-result' && dbErrors.length > 0) {
    payload = {
      ...obj,
      ok: false,
      dbProbeErrors: dbErrors.length,
      dbProbeErrorNote:
        'DB probe(s) failed — zero-write / side-effect assertions did not run',
    };
  }
  process.stdout.write(
    JSON.stringify({ ts: new Date().toISOString(), ...payload }) + '\n'
  );
}

/** Resolve seeded ids written by seed-qa-user.ts. Returns null when
 *  the file is missing — the caller decides whether that's a hard
 *  failure (auth-required walkers) or a no-op (public pages). */
export function readSeededIds() {
  const path = resolve(
    __dirname,
    '..',
    '..',
    'fixtures',
    'seeded-ids.json'
  );
  try {
    return JSON.parse(readFileSync(path, 'utf-8'));
  } catch {
    return null;
  }
}

// ──────────────────────────────────────────────────────────────────────
// DB probe plumbing — FAILS LOUDLY (full-app audit 2026-07-24).
// ----------------------------------------------------------------------
// Every DB helper below used to be `try { … } catch { return null }`. A
// malformed query therefore produced the same result as "nothing changed",
// so the zero-write / expected-side-effect assertions that define the
// transactional walker tier silently stopped running. The 2026-07-24 sweep
// reported 30/30 walkers OK while emitting 14 Postgres errors — unquoted
// camelCase identifiers ("updatedat"/"userid" do not exist) and a doubled
// LIMIT. Errors are now collected and surfaced so the walker can fail.
// ──────────────────────────────────────────────────────────────────────
const dbErrors = [];

/** Errors recorded by the DB probes since the last reset. A non-empty list
 *  MUST fail the walker — a probe that errored proves nothing. */
export function getDbErrors() {
  return [...dbErrors];
}
export function resetDbErrors() {
  dbErrors.length = 0;
}

/** Run one SQL statement against the resolved (non-prod by default) DB.
 *  Returns trimmed stdout, or null after recording the failure. */
function psql(sql, context) {
  try {
    return execSync(
      `docker exec ${DB_CONTAINER} psql -U ${DB_USER} -d ${DB_NAME} -tA -c ${JSON.stringify(sql)}`,
      { encoding: 'utf-8', stdio: ['ignore', 'pipe', 'pipe'] }
    ).trim();
  } catch (err) {
    const stderr = (err && err.stderr ? String(err.stderr) : String(err && err.message)).trim();
    const record = { context, sql, error: stderr.slice(0, 400) };
    dbErrors.push(record);
    // Emit on the NDJSON stream so the failure reaches the report even when a
    // walker forgets to check getDbErrors(). sweep-all.mjs fails any walker
    // that emits one of these — a probe that errored proves nothing, and
    // "silently proves nothing" is exactly the bug this replaces.
    emit({ event: 'db-probe-error', ...record });
    return null;
  }
}

/** Pull the visit's current mutable state for diffing. */
export function snapshotVisit(visitId, label) {
  if (!visitId) return null;
  return psql(
    `SELECT row_to_json(t) FROM (SELECT id, status::text, "signedAt"::text, ` +
      `LENGTH(COALESCE("soapDraft",'')) AS sd, LENGTH(COALESCE("soapFinal",'')) AS sf, ` +
      `"cptCodes"::text AS cpt, "updatedAt"::text AS updated ` +
      `FROM transcribe_visits WHERE id='${visitId}') t;`,
    `snapshotVisit:${label ?? visitId}`
  );
}

/** Count audit rows for a visit since the last 10 minutes — used to
 *  detect "did this click write an audit row?" without parsing the
 *  full audit log. Note: audit_logs uses snake_case `timestamp`, not
 *  Prisma's camel-case `createdAt`. Don't quote it. */
export function snapshotAuditCount(visitId) {
  if (!visitId) return 0;
  const out = psql(
    `SELECT COUNT(*) FROM audit_logs WHERE "targetId"='${visitId}' ` +
      `AND timestamp > NOW() - INTERVAL '10 minutes';`,
    `snapshotAuditCount:${visitId}`
  );
  if (out === null) return 0; // failure already recorded in dbErrors
  return parseInt(out, 10) || 0;
}

/** Settled-count variant of `snapshotAuditCount` — closes F-15 from the
 *  v3.2 discovery report. Product code emits audit rows fire-and-forget
 *  (`void logAudit({ ... })`), so on slow VPSes the row write can lag
 *  behind the walker's post-click read by a few hundred ms. The naive
 *  "snapshot before / snapshot after" comparison would then return
 *  delta=0 and surface a false-negative finding.
 *
 *  This helper polls until two consecutive reads agree:
 *
 *    1. Read count
 *    2. Wait 250 ms
 *    3. Read again
 *    4. If different (write in flight), loop up to `maxAttempts`
 *    5. Once two consecutive reads match, return that count
 *    6. Hard cap at ~1.25s to avoid stalling the walker
 *
 *  Returns the settled count. Falls back to the last-read count when
 *  the cap is hit (better than throwing — the walker can still report
 *  a result).
 *
 *  Test: see qa-interaction-auditor/tests/audit-settle.test.mjs.
 */
export function snapshotAuditCountWithSettle(
  visitId,
  { maxAttempts = 5, settleMs = 250 } = {}
) {
  if (!visitId) return 0;
  let prev = snapshotAuditCount(visitId);
  for (let i = 0; i < maxAttempts; i += 1) {
    // Synchronous spin — execSync gives us a sync API, and the walker
    // is already serial per click, so a 250 ms sleep is acceptable.
    // We use `sh -c "sleep 0.25"` because Node has no built-in sync
    // sleep and busy-loops would be wasteful + lock the event loop
    // longer than a real sleep.
    try {
      execSync(`sleep ${settleMs / 1000}`);
    } catch {
      // sleep failed — treat as already-settled
      return prev;
    }
    const next = snapshotAuditCount(visitId);
    if (next === prev) return next;
    prev = next;
  }
  return prev;
}

/** Recent Caddy mutations within the last `sinceSeconds`. Used for
 *  classifying whether a click fired a server-side write. Filters out
 *  static-asset and Next.js internal POSTs. */
export function recentMutations(sinceSeconds = 10) {
  // No container named for this target → do not scrape anything. Reading
  // production's ingress log while driving QA is worse than reading none.
  if (!INGRESS_LOG_CONTAINER) return [];
  try {
    const raw = execSync(
      `docker logs ${INGRESS_LOG_CONTAINER} --since "${sinceSeconds}s" 2>&1`,
      { encoding: 'utf-8', maxBuffer: 16 * 1024 * 1024 }
    );
    const muts = [];
    for (const line of raw.split('\n')) {
      if (!line.includes('"method"')) continue;
      const idx = line.indexOf('{');
      if (idx === -1) continue;
      try {
        const j = JSON.parse(line.slice(idx));
        const method = j?.request?.method;
        if (!['POST', 'PATCH', 'PUT', 'DELETE'].includes(method)) continue;
        const uri = j?.request?.uri ?? '';
        if (uri.startsWith('/_next/') || uri.startsWith('/static/')) continue;
        muts.push({ method, uri, status: j.status });
      } catch {
        // skip malformed line
      }
    }
    return muts;
  } catch (err) {
    // A named container we could not read is "we did not look", not
    // "nothing happened". Record it so ingressLogSource() stops
    // claiming the signal was available.
    ingressLogUnavailableReason = `docker logs ${INGRESS_LOG_CONTAINER} failed: ${err.message}`;
    return [];
  }
}

/** Per-pattern click classification. */
export function classifyClick({ response, mutations, dbBefore, dbAfter, auditDelta }) {
  const allMuts = [
    ...(response ? [{ status: response.status }] : []),
    ...mutations,
  ];
  const dbChanged = dbBefore !== dbAfter && dbBefore !== null;
  const success = allMuts.find((m) => m.status >= 200 && m.status < 300);
  const fail4xx = allMuts.find((m) => m.status >= 400 && m.status < 500);
  const fail5xx = allMuts.find((m) => m.status >= 500);

  if (allMuts.length === 0) {
    return dbChanged || auditDelta > 0 ? 'OK_NO_NETWORK' : 'NO_NETWORK_FIRED';
  }
  if (fail5xx) return `HTTP_${fail5xx.status}`;
  if (fail4xx && !success) return `HTTP_${fail4xx.status}`;
  if (success && !dbChanged && auditDelta === 0) {
    return 'PRETEND_SUCCESS_FALLBACK';
  }
  return 'OK';
}

/** Launch headless Chromium with the dark-mode + reduced-motion
 *  context the agent uses everywhere. */
export async function launchBrowser() {
  return chromium.launch({ headless: true });
}

export async function newAppContext(browser, opts = {}) {
  const ctx = await browser.newContext({
    baseURL: APP_BASE,
    colorScheme: 'dark',
    reducedMotion: 'reduce',
    // When a sweep-all run has already cached a logged-in session at
    // this path, reuse it. Per-walker login is the v2 default and
    // tripped a rate-limit on /login after ~3 sequential walkers; the
    // session reuse path is the v3.1 fix for that.
    storageState:
      opts.storageState !== undefined ? opts.storageState : undefined,
  });
  return ctx;
}

export async function newMarketingContext(browser) {
  return browser.newContext({
    baseURL: MARKETING_BASE,
    colorScheme: 'dark',
    reducedMotion: 'reduce',
  });
}

/** Login as the seeded QA user. Required env: QA_AUDITOR_PASSWORD.
 *  Throws if the post-submit URL is still /login (login refused). */
export async function login(page) {
  const password = process.env.QA_AUDITOR_PASSWORD;
  if (!password) {
    throw new Error(
      'QA_AUDITOR_PASSWORD env unset — see fixtures/test-user.md'
    );
  }
  await page.goto('/login', { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.fill('input[type="email"]', TEST_EMAIL);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');

  // WAIT ON THE URL, NOT ON A NAVIGATION.
  //
  // The login form is `<form action={formAction}>` — a React 19 server action.
  // It resolves to a SOFT navigation, so no `load` event ever fires, and
  // `page.waitForURL(...)` (which defaults to waitUntil:'load') sat there for
  // its full timeout while the login had actually SUCCEEDED. The failure read
  // as "login refused" and was neither: the walker was waiting for an event
  // this app does not emit on this path.
  //
  // Polling the pathname is what we actually mean and is navigation-shape
  // agnostic — it works for a hard redirect and a soft one alike.
  await page
    .waitForFunction(() => !window.location.pathname.startsWith('/login'), null, {
      timeout: 20_000,
      polling: 250,
    })
    .catch(() => {
      throw new Error(
        `login did not leave /login within 20s (url=${page.url()}) — ` +
          'check QA_AUDITOR_EMAIL / QA_AUDITOR_PASSWORD for this environment'
      );
    });
}

/** Returns a path to a cached Playwright `storageState` JSON file for
 *  the QA test user. First call within a sweep launches a one-shot
 *  browser, logs in, calls `ctx.storageState({ path })`, and writes
 *  the cookies + localStorage to disk. Subsequent calls (inside the
 *  same sweep, sharing QA_SWEEP_RUN_ID) just return the path —
 *  walkers create contexts with `storageState: <path>` and skip the
 *  login flow entirely.
 *
 *  Auto-invalidation:
 *   - File age > SESSION_TTL_MS (30 min) → re-login + overwrite.
 *   - Caller passes `{ forceFresh: true }` after detecting a /login
 *     redirect mid-walk → re-login + overwrite.
 *
 *  Returns the resolved path (never undefined). Throws if login
 *  itself fails — that's a real error the orchestrator should
 *  surface, not paper over with a stub session.
 */
export async function getOrCreateAuthState({ forceFresh = false } = {}) {
  const path = sessionPath();

  if (!forceFresh && existsSync(path)) {
    const ageMs = Date.now() - statSync(path).mtimeMs;
    if (ageMs < SESSION_TTL_MS) {
      return path;
    }
  }
  // Stale or missing — re-login.
  if (existsSync(path)) {
    try { unlinkSync(path); } catch { /* ignore */ }
  }

  const browser = await launchBrowser();
  try {
    const ctx = await browser.newContext({
      baseURL: APP_BASE,
      colorScheme: 'dark',
      reducedMotion: 'reduce',
    });
    const page = await ctx.newPage();
    await login(page);
    await ctx.storageState({ path });
    await ctx.close();
  } finally {
    await browser.close();
  }
  return path;
}

/** Force-invalidate the cached session file. Walkers call this when
 *  they detect a /login redirect mid-walk — the next
 *  getOrCreateAuthState() call re-logs-in. */
export function invalidateAuthState() {
  const path = sessionPath();
  if (existsSync(path)) {
    try { unlinkSync(path); } catch { /* ignore */ }
  }
}

/** Standard page-load smoke: navigate, wait for body, snapshot
 *  interactive-element counts. Each per-page walker calls this and
 *  may add page-specific assertions on top. */
export async function smokeLoad(page, url, opts = {}) {
  const t0 = Date.now();
  let loadErr = null;
  try {
    await page.goto(url, {
      waitUntil: opts.waitUntil ?? 'networkidle',
      timeout: opts.timeout ?? 20_000,
    });
  } catch (e) {
    loadErr = e.message;
  }
  await page.waitForTimeout(opts.settleMs ?? 400);

  const snapshot = await page.evaluate(() => {
    const interactive = document.querySelectorAll(
      'button, [role="button"], a[href], input, textarea, select'
    );
    const visible = Array.from(interactive).filter((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    });
    return {
      url: window.location.href,
      title: document.title,
      bodyTextLength: (document.body.innerText ?? '').length,
      interactiveCount: interactive.length,
      visibleInteractiveCount: visible.length,
      hasH1: !!document.querySelector('h1'),
      h1Text:
        (document.querySelector('h1')?.textContent ?? '').trim().slice(0, 80) ||
        null,
    };
  });

  return {
    durationMs: Date.now() - t0,
    loadErr,
    ...snapshot,
  };
}

/** Convenience: full smoke walker shape used by the stub walkers.
 *  Public-page version (no auth). */
export async function smokeWalkPublic({ name, url, base = 'marketing' }) {
  const browser = await launchBrowser();
  try {
    const ctx =
      base === 'app'
        ? await newAppContext(browser)
        : await newMarketingContext(browser);
    const page = await ctx.newPage();

    emit({ event: 'walker-start', name, url });
    const result = await smokeLoad(page, url);
    emit({
      event: 'walker-result',
      name,
      url,
      ok: !result.loadErr,
      ...result,
    });
    emit({ event: 'walker-end', name });

    await ctx.close();
  } finally {
    await browser.close();
  }
}

/** Convenience: smoke walker for an authenticated app page. Reuses
 *  a cached storageState across walkers in the same sweep run so we
 *  don't trip the /login rate limiter (the v2 issue).
 *
 *  If the page-load redirects back to /login, the walker assumes the
 *  cached session expired mid-sweep, invalidates it, fetches a fresh
 *  one, and retries the load once. A second redirect to /login is
 *  reported as a real failure (e.g. the user got locked out, the
 *  product entitlement got revoked, etc.).
 */
export async function smokeWalkAuth({ name, url }) {
  emit({ event: 'walker-start', name, url });

  // Acquire a cached/fresh session BEFORE launching the walker
  // browser so the per-walker context starts already-authenticated.
  let storagePath;
  try {
    storagePath = await getOrCreateAuthState();
  } catch (err) {
    emit({
      event: 'walker-result',
      name,
      url,
      ok: false,
      loadErr: err.message,
      stage: 'login',
    });
    emit({ event: 'walker-end', name });
    return;
  }

  const browser = await launchBrowser();
  try {
    let ctx = await newAppContext(browser, { storageState: storagePath });
    let page = await ctx.newPage();

    let result = await smokeLoad(page, url);

    // Mid-sweep session expiry: page bounced to /login. Drop the
    // stale state, fetch fresh, retry once.
    const looksRedirectedToLogin =
      typeof result.url === 'string' && result.url.includes('/login');
    if (looksRedirectedToLogin) {
      emit({
        event: 'walker-session-refresh',
        name,
        reason: 'redirect-to-login — invalidating cached storageState',
      });
      await ctx.close();
      invalidateAuthState();
      try {
        storagePath = await getOrCreateAuthState({ forceFresh: true });
      } catch (err) {
        emit({
          event: 'walker-result',
          name,
          url,
          ok: false,
          loadErr: err.message,
          stage: 'login-retry',
        });
        emit({ event: 'walker-end', name });
        return;
      }
      ctx = await newAppContext(browser, { storageState: storagePath });
      page = await ctx.newPage();
      result = await smokeLoad(page, url);
    }

    emit({
      event: 'walker-result',
      name,
      url,
      ok: !result.loadErr && !(typeof result.url === 'string' && result.url.includes('/login')),
      ...result,
    });
    emit({ event: 'walker-end', name });

    await ctx.close();
  } finally {
    await browser.close();
  }
}

// ============================================================================
// deepWalk — element-by-element interaction walk for a target page
// ----------------------------------------------------------------------------
// Foundation helper for v3.2 + v3.3 deepening. Each walker passes a
// page (already navigated to its target URL by the caller), an array
// of selectors to click, and the DB tables whose state we care about.
// For each selector we:
//   1. Snapshot DB tables BEFORE the click
//   2. Snapshot Caddy access-log offset BEFORE
//   3. Click the locator (or skip if not visible / disabled)
//   4. Wait for network-idle + a brief settle (configurable)
//   5. Snapshot DB tables AFTER
//   6. Snapshot Caddy log AFTER (delta only — recent N seconds)
//   7. Classify the click outcome:
//      - OK                    — DB write + audit row + UI update
//      - NO_NETWORK_FIRED      — pure UI / orphan dispatcher
//      - PRETEND_SUCCESS_FALLBACK — 200 status + no DB write + no audit
//      - HTTP_4xx / HTTP_5xx   — server rejected
//      - VISUAL_ONLY           — DOM mutation without network or DB
//      - DISABLED / HIDDEN     — element wasn't clickable
//   8. Emit one NDJSON record per click
//
// The flagship sweep-visit-page.mjs is the proof-of-shape — it
// refactored its bespoke walking logic into deepWalk + selector list.
// New v3.2 walkers (dashboard, visits-list, settings, etc.) wire
// their per-page selectors in the same shape.
// ============================================================================

/** Snapshot a small set of postgres tables/columns. The caller passes
 *  table names; we run a row_to_json query per (table, idColumn)
 *  pair. Returns a Map keyed by `${table}:${id}`. Skips silently when
 *  docker exec fails — the diff downstream just sees null. */
export function snapshotTables(spec) {
  // spec: Array<{ table: string, where: string }>
  const out = {};
  for (const entry of spec) {
    // Callers legitimately pass an ordered/limited predicate such as
    // `TRUE ORDER BY "updatedAt" DESC LIMIT 5`. Blindly appending our own
    // LIMIT produced `… LIMIT 5 LIMIT 1` → `syntax error at or near "LIMIT"`,
    // which the old bare catch swallowed. Only add the guard LIMIT when the
    // caller has not already bounded the query.
    const hasLimit = /\blimit\b/i.test(entry.where);
    const json = psql(
      `SELECT row_to_json(t) FROM (SELECT * FROM ${entry.table} WHERE ${entry.where}` +
        `${hasLimit ? '' : ' LIMIT 1'}) t;`,
      `snapshotTables:${entry.table}`
    );
    out[entry.table] = json || null;
  }
  return out;
}

// (snapshotAuditCount is defined earlier in this file — reused here.)

/** Snapshot COUNTS rather than rows. Added for the Rounds board walker
 *  (item F, 2026-08-02), and preferable to snapshotTables wherever the
 *  question is "did anything get written" rather than "did this row
 *  change":
 *
 *   - snapshotTables does `SELECT *`, so on transcribe_visits it pulls
 *     soapDraft/soapFinal into the walker's memory to answer a yes/no
 *     question. A count never touches clinical text.
 *   - it also LIMITs to one row, so an INSERT that lands outside the
 *     ordered window is invisible. A count sees every row.
 *
 *  Returns { [label]: number|null }. A null is a FAILED probe, already
 *  recorded in dbErrors — emit() will downgrade the walker's ok for it.
 *  Callers must treat null as "did not measure", never as zero. */
export function snapshotCounts(spec) {
  const out = {};
  for (const entry of spec) {
    const raw = psql(
      `SELECT COUNT(*) FROM ${entry.table} WHERE ${entry.where};`,
      `snapshotCounts:${entry.label ?? entry.table}`
    );
    out[entry.label ?? entry.table] =
      raw === null ? null : (parseInt(raw, 10) ?? null);
  }
  return out;
}

/** Locate an element by a Playwright-style selector spec. Spec can be
 *  a string (CSS) or `{ role, name }` (accessibility). Returns the
 *  Locator or null when nothing is visible / matching. */
async function locateBySpec(page, spec) {
  if (typeof spec === 'string') {
    const loc = page.locator(spec).first();
    return (await loc.count()) > 0 ? loc : null;
  }
  if (typeof spec === 'object' && spec !== null) {
    if (spec.role) {
      const loc = page.getByRole(spec.role, spec.name ? { name: spec.name } : {}).first();
      return (await loc.count()) > 0 ? loc : null;
    }
    if (spec.text) {
      const loc = page.getByText(spec.text, { exact: !!spec.exact }).first();
      return (await loc.count()) > 0 ? loc : null;
    }
    if (spec.testId) {
      const loc = page.getByTestId(spec.testId).first();
      return (await loc.count()) > 0 ? loc : null;
    }
  }
  return null;
}

/** Click a single selector + classify the outcome. Used by deepWalk
 *  but also exported so per-walker code can call it for ad-hoc
 *  click-and-classify steps that don't fit the bulk-walk shape. */
export async function clickAndClassify(page, opts) {
  const {
    name = 'click',
    selector,
    dbSnapshotSpec = [],
    auditTargetId = null,
    settleMs = 800,
    networkTimeoutMs = 5000,
    expectedAuditAction = null,
  } = opts;

  const locator = await locateBySpec(page, selector);
  if (!locator) {
    return {
      name,
      classification: 'HIDDEN_OR_MISSING',
      note: 'selector matched no visible element',
    };
  }
  if (await locator.isDisabled().catch(() => false)) {
    return { name, classification: 'DISABLED' };
  }

  const dbBefore = snapshotTables(dbSnapshotSpec);
  const auditBefore = snapshotAuditCount(auditTargetId);
  const domBeforeHash = await page.evaluate(
    () => document.body.innerText?.length ?? 0
  );

  let response = null;
  let clickErr = null;
  try {
    [response] = await Promise.all([
      page
        .waitForResponse(
          (r) =>
            r.request().method() !== 'GET' &&
            (r.url().includes('/api/') || r.url().includes('/visits/')),
          { timeout: networkTimeoutMs }
        )
        .catch(() => null),
      locator.click({ timeout: 4000 }),
    ]);
  } catch (err) {
    clickErr = err.message;
  }
  await page.waitForTimeout(settleMs);

  const dbAfter = snapshotTables(dbSnapshotSpec);
  // F-15: void logAudit() in product code is fire-and-forget; the row
  // write can lag the post-click read by a few hundred ms. Use the
  // settled variant so the walker doesn't false-negative on slow VPS.
  const auditAfter = snapshotAuditCountWithSettle(auditTargetId);
  const muts = recentMutations(12);
  const newMuts = muts; // recentMutations already filters to short window
  const responseSummary = response
    ? {
        status: response.status(),
        url: response.url(),
        method: response.request().method(),
      }
    : null;

  const dbChanged =
    JSON.stringify(dbBefore) !== JSON.stringify(dbAfter);
  const auditDelta = auditAfter - auditBefore;
  const domAfterHash = await page.evaluate(
    () => document.body.innerText?.length ?? 0
  );
  const domMutated = domAfterHash !== domBeforeHash;

  let classification;
  const status = responseSummary?.status ?? null;
  if (clickErr) {
    classification = 'CLICK_THREW';
  } else if (status === null && newMuts.length === 0) {
    if (dbChanged || auditDelta > 0) classification = 'OK_NO_NETWORK';
    else if (domMutated) classification = 'VISUAL_ONLY';
    else classification = 'NO_NETWORK_FIRED';
  } else if (status >= 500) {
    classification = `HTTP_${status}`;
  } else if (status >= 400) {
    classification = `HTTP_${status}`;
  } else if (status >= 200 && status < 300) {
    if (!dbChanged && auditDelta === 0) classification = 'PRETEND_SUCCESS_FALLBACK';
    else classification = 'OK';
  } else {
    classification = `HTTP_${status ?? 'UNKNOWN'}`;
  }

  return {
    name,
    classification,
    response: responseSummary,
    networkMutationCount: newMuts.length,
    dbChanged,
    auditDelta,
    domMutated,
    expectedAuditAction,
    clickErr,
  };
}

/** Bulk: walk a list of selectors against a single page; emit one
 *  NDJSON record per click. Each entry in `selectors` is either a
 *  string (uses the same name + dbSnapshotSpec for all) or an object
 *  `{ name, selector, dbSnapshotSpec?, auditTargetId? }` for per-
 *  selector overrides. Caller is responsible for emit/save semantics
 *  beyond the click stream itself.
 */
export async function deepWalk({
  page,
  selectors,
  dbSnapshotSpec = [],
  auditTargetId = null,
  settleMs = 800,
}) {
  const records = [];
  for (const entry of selectors) {
    const opts =
      typeof entry === 'string'
        ? { name: entry, selector: entry, dbSnapshotSpec, auditTargetId }
        : { dbSnapshotSpec, auditTargetId, ...entry };
    const result = await clickAndClassify(page, { ...opts, settleMs });
    emit({ event: 'deep-walk-click', ...result });
    records.push(result);
  }
  return records;
}

export { APP_BASE, MARKETING_BASE, TEST_EMAIL };
