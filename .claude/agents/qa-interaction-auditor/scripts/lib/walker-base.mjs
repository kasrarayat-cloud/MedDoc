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
const APP_BASE = process.env.QA_AUDITOR_APP_URL ?? 'https://app.quillmd.com';
const MARKETING_BASE =
  process.env.QA_AUDITOR_MARKETING_URL ?? 'https://quillmd.com';

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
 *  the unified report without re-parsing prose output. */
export function emit(obj) {
  process.stdout.write(
    JSON.stringify({ ts: new Date().toISOString(), ...obj }) + '\n'
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

/** Pull the visit's current mutable state for diffing. */
export function snapshotVisit(visitId, label) {
  if (!visitId) return null;
  try {
    return execSync(
      `docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -tA -c \
"SELECT row_to_json(t) FROM (SELECT id, status::text, \\\"signedAt\\\"::text, LENGTH(COALESCE(\\\"soapDraft\\\",'')) AS sd, LENGTH(COALESCE(\\\"soapFinal\\\",'')) AS sf, \\\"cptCodes\\\"::text AS cpt, \\\"updatedAt\\\"::text AS updated FROM transcribe_visits WHERE id='${visitId}') t;"`,
      { encoding: 'utf-8' }
    ).trim();
  } catch {
    return null;
  }
}

/** Count audit rows for a visit since the last 10 minutes — used to
 *  detect "did this click write an audit row?" without parsing the
 *  full audit log. Note: audit_logs uses snake_case `timestamp`, not
 *  Prisma's camel-case `createdAt`. Don't quote it. */
export function snapshotAuditCount(visitId) {
  if (!visitId) return 0;
  try {
    const out = execSync(
      `docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -tA -c \
"SELECT COUNT(*) FROM audit_logs WHERE \\\"targetId\\\"='${visitId}' AND timestamp > NOW() - INTERVAL '10 minutes';"`,
      { encoding: 'utf-8' }
    );
    return parseInt(out.trim(), 10) || 0;
  } catch {
    return 0;
  }
}

/** Recent Caddy mutations within the last `sinceSeconds`. Used for
 *  classifying whether a click fired a server-side write. Filters out
 *  static-asset and Next.js internal POSTs. */
export function recentMutations(sinceSeconds = 10) {
  try {
    const raw = execSync(
      `docker logs meddoc-pro-caddy-1 --since "${sinceSeconds}s" 2>&1`,
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
  } catch {
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
  await Promise.all([
    page.waitForURL((u) => !u.pathname.startsWith('/login'), {
      timeout: 20_000,
    }),
    page.click('button[type="submit"]'),
  ]);
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
    try {
      const json = execSync(
        `docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -tA -c \
"SELECT row_to_json(t) FROM (SELECT * FROM ${entry.table} WHERE ${entry.where} LIMIT 1) t;"`,
        { encoding: 'utf-8' }
      ).trim();
      out[entry.table] = json || null;
    } catch {
      out[entry.table] = null;
    }
  }
  return out;
}

// (snapshotAuditCount is defined earlier in this file — reused here.)

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
  const auditAfter = snapshotAuditCount(auditTargetId);
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
