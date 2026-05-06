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
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const TEST_EMAIL = process.env.QA_AUDITOR_EMAIL ?? 'qa-auditor@quillmd.test';
const APP_BASE = process.env.QA_AUDITOR_APP_URL ?? 'https://app.quillmd.com';
const MARKETING_BASE =
  process.env.QA_AUDITOR_MARKETING_URL ?? 'https://quillmd.com';

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

export async function newAppContext(browser) {
  const ctx = await browser.newContext({
    baseURL: APP_BASE,
    colorScheme: 'dark',
    reducedMotion: 'reduce',
    storageState: undefined,
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

/** Convenience: smoke walker for an authenticated app page. */
export async function smokeWalkAuth({ name, url }) {
  const browser = await launchBrowser();
  try {
    const ctx = await newAppContext(browser);
    const page = await ctx.newPage();

    emit({ event: 'walker-start', name, url });

    try {
      await login(page);
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
      await ctx.close();
      return;
    }

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

export { APP_BASE, MARKETING_BASE, TEST_EMAIL };
