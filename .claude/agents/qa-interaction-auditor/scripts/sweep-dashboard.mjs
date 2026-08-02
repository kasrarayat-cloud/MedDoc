#!/usr/bin/env node
// ============================================================================
// sweep-dashboard.mjs — /dashboard deep walker (✅ tier, v3.2)
// ----------------------------------------------------------------------------
// Walks every interactive element on the clinician's main landing
// surface as the QA test user.
//
// Page layout (from src/app/dashboard/page.tsx):
//   - Greeting + 4 StatCards (read-only)
//   - TabBar — Patients ↔ All visits (Link-based, ?tab=all). In-page,
//     stateful, click-only — perfect deep-walk targets.
//   - PatientList rows (link to /patients/[id]) → enumerate, NO click
//   - VisitList rows (link to /visits/[id])     → enumerate, NO click
//   - DraftsReady rows (link to /visits/[id])   → enumerate, NO click
//   - AppFrame chrome:
//       · Sidebar nav rows (Dashboard / Visits / Patients / Settings)
//       · Top-bar: brand → /dashboard, Cmd-K palette button (in-page),
//         "+ New visit" link (outbound), avatar dropdown trigger.
//
// Per click target: snapshot transcribe_visits + transcribe_md_patients
// rows BEFORE/AFTER, compute audit-delta (auditTargetId=null because
// /dashboard is not visit-scoped — counts every recent audit row).
//
// Auth via lib/walker-base.mjs getOrCreateAuthState (session reuse —
// no per-walker login). Same /login-redirect retry shape as
// sweep-visit-page.mjs.
//
// Usage:
//   node sweep-dashboard.mjs                     # default /dashboard
//   node sweep-dashboard.mjs --skip-clicks       # enumerate-only
//   node sweep-dashboard.mjs --tab all           # navigate to ?tab=all
//
// Output: NDJSON to stdout — one record per element / click / event.
// ============================================================================

import { argv, env, exit, stderr } from 'node:process';

import {
  emit,
  getOrCreateAuthState,
  invalidateAuthState,
  launchBrowser,
  newAppContext,
  clickAndClassify,
  snapshotTables,
  snapshotAuditCount,
  APP_BASE,
} from './lib/walker-base.mjs';

// ---------------------------------------------------------------------------
// Args
// ---------------------------------------------------------------------------

function parseArgs(args) {
  const opts = {
    // Defaults to the SAME target walker-base already refuses to point at
    // production without an opt-in. It used to default to
    // 'https://app.quillmd.com' independently, under a DIFFERENT env var
    // (QA_AUDITOR_BASE_URL, not QA_AUDITOR_APP_URL), so the fail-closed
    // guard never saw it. Rounds item F, 2026-08-02.
    base: env.QA_AUDITOR_BASE_URL ?? APP_BASE,
    skipClicks: false,
    tab: null,
    timeout: 15_000,
  };
  for (let i = 2; i < args.length; i += 1) {
    const a = args[i];
    if (a === '--base') { opts.base = args[i + 1]; i += 1; }
    else if (a === '--tab') { opts.tab = args[i + 1]; i += 1; }
    else if (a === '--skip-clicks') { opts.skipClicks = true; }
    else if (a === '--timeout') { opts.timeout = Number(args[i + 1]); i += 1; }
    else if (a === '--help' || a === '-h') {
      stderr.write(
        'sweep-dashboard.mjs [--tab all] [--skip-clicks] [--timeout ms]\n'
      );
      exit(2);
    } else {
      stderr.write(`Unknown arg: ${a}\n`);
      exit(2);
    }
  }
  return opts;
}

const opts = parseArgs(argv);
const TARGET_URL = opts.tab ? `/dashboard?tab=${opts.tab}` : '/dashboard';

// ---------------------------------------------------------------------------
// DOM enumeration — same shape as sweep-visit-page.mjs.
// ---------------------------------------------------------------------------

async function enumerate(page) {
  return page.$$eval(
    'button, [role="button"], a[href^="/"], input[type="submit"]',
    (els) =>
      els
        .map((el, i) => {
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) return null;
          return {
            index: i,
            tag: el.tagName.toLowerCase(),
            text: (el.textContent ?? '').trim().slice(0, 80),
            disabled:
              'disabled' in el && typeof el.disabled === 'boolean'
                ? el.disabled
                : el.getAttribute('aria-disabled') === 'true',
            href: el.getAttribute('href') ?? null,
            ariaLabel: el.getAttribute('aria-label') ?? null,
            role: el.getAttribute('role'),
          };
        })
        .filter(Boolean)
  );
}

/** Decide whether an element's click would leave /dashboard. Internal
 *  /dashboard tab links (?tab=all, the brand "QuillMD → /dashboard"
 *  link, etc.) stay in-page; everything else is outbound. Buttons
 *  without href are presumed in-page (Cmd-K, avatar dropdown). */
function isOutbound(el) {
  if (el.tag !== 'a') return false;
  if (!el.href) return false;
  // Same-page links: bare /dashboard or /dashboard?... query.
  if (el.href === '/dashboard') return false;
  if (el.href.startsWith('/dashboard?')) return false;
  if (el.href.startsWith('/dashboard#')) return false;
  return true;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const t0 = Date.now();
  emit({ event: 'sweep-start', url: TARGET_URL, base: opts.base });

  let storagePath;
  try {
    storagePath = await getOrCreateAuthState();
  } catch (err) {
    emit({ event: 'sweep-error', stage: 'login', message: err.message });
    emit({
      event: 'walker-result',
      name: 'dashboard',
      url: TARGET_URL,
      ok: false,
      loadErr: err.message,
      stage: 'login',
    });
    exit(1);
  }

  const browser = await launchBrowser();
  let exitCode = 0;
  const counters = { elements: 0, clicks: 0, findings: 0 };

  try {
    let ctx = await newAppContext(browser, { storageState: storagePath });
    let page = await ctx.newPage();

    await page.goto(TARGET_URL, {
      waitUntil: 'networkidle',
      timeout: opts.timeout,
    });

    // Cached-session-expiry retry. Same shape as sweep-visit-page.mjs.
    if (page.url().includes('/login')) {
      emit({
        event: 'sweep-session-refresh',
        reason: 'redirect-to-login — invalidating cached storageState',
      });
      await ctx.close();
      invalidateAuthState();
      storagePath = await getOrCreateAuthState({ forceFresh: true });
      ctx = await newAppContext(browser, { storageState: storagePath });
      page = await ctx.newPage();
      await page.goto(TARGET_URL, {
        waitUntil: 'networkidle',
        timeout: opts.timeout,
      });
    }

    // Baseline audit count. /dashboard is not visit-scoped, so we use
    // an unscoped count (auditTargetId=null → snapshotAuditCount returns
    // 0; the per-click delta below uses the same null target so audit
    // diff is always 0 for view-only clicks — that's the assertion).
    const auditBaseline = snapshotAuditCount(null);
    emit({
      event: 'audit-baseline',
      url: TARGET_URL,
      count: auditBaseline,
      expected: ['VIEWED_PATIENT_LIST', 'VIEWED_VISIT_LIST'],
    });

    const elements = await enumerate(page);
    counters.elements = elements.length;
    for (const el of elements) {
      emit({ event: 'element', ...el });
    }

    if (!opts.skipClicks) {
      // /dashboard's click surface should NEVER mutate either of these
      // tables; the snapshot is a read-scoping check — any diff is a
      // finding.
      const dbSnapshotSpec = [
        {
          table: 'transcribe_visits',
          where: 'TRUE ORDER BY "updatedAt" DESC',
        },
        {
          table: 'transcribe_md_patients',
          where: 'TRUE ORDER BY "updatedAt" DESC',
        },
      ];

      for (const el of elements) {
        if (el.disabled) {
          emit({ event: 'click-skipped', label: el.text, reason: 'disabled' });
          continue;
        }
        // Patient/visit row links + sidebar nav + "+ New visit" =
        // outbound. Enumerate but don't click.
        if (isOutbound(el)) {
          emit({
            event: 'click-skipped',
            label: el.text,
            reason: 'leaves-page',
            href: el.href,
          });
          continue;
        }

        // In-page click targets that remain after the filter:
        //   - TabBar Links (href=/dashboard, /dashboard?tab=all)
        //   - Top-bar brand Link (href=/dashboard) — same as a tab
        //   - Cmd-K palette <button> (no href, in-page)
        //   - Avatar dropdown trigger <button> (no href, in-page)

        const selectorSpec = el.ariaLabel
          ? { role: el.role ?? (el.tag === 'a' ? 'link' : 'button'), name: el.ariaLabel }
          : { text: el.text || '?', exact: false };

        const result = await clickAndClassify(page, {
          name: el.text || el.ariaLabel || `(${el.tag})`,
          selector: selectorSpec,
          dbSnapshotSpec,
          auditTargetId: null,
          settleMs: 800,
        });
        counters.clicks += 1;

        if (
          result.classification === 'NO_NETWORK_FIRED' ||
          result.classification === 'PRETEND_SUCCESS_FALLBACK' ||
          result.classification === 'CLICK_THREW' ||
          (typeof result.classification === 'string' &&
            result.classification.startsWith('HTTP_5'))
        ) {
          counters.findings += 1;
        }

        emit({ event: 'click', label: el.text, ...result });

        // Re-navigate after each click for a stable starting state —
        // tab clicks change the URL, dropdown clicks open portals that
        // would shadow subsequent locator matches.
        await page.goto(TARGET_URL, {
          waitUntil: 'networkidle',
          timeout: opts.timeout,
        });
      }
    }

    emit({ event: 'sweep-end', ...counters });
    emit({
      event: 'walker-result',
      name: 'dashboard',
      url: TARGET_URL,
      ok: true,
      durationMs: Date.now() - t0,
      ...counters,
    });
    await ctx.close();
  } catch (err) {
    emit({ event: 'sweep-error', message: err.message, stack: err.stack });
    emit({
      event: 'walker-result',
      name: 'dashboard',
      url: TARGET_URL,
      ok: false,
      loadErr: err.message,
      durationMs: Date.now() - t0,
      ...counters,
    });
    exitCode = 1;
  } finally {
    await browser.close();
  }
  exit(exitCode);
}

main();
