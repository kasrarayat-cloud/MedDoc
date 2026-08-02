#!/usr/bin/env node
// ============================================================================
// sweep-visits-list.mjs — /visits deep walker (✅ tier, v3.2)
// ----------------------------------------------------------------------------
// Walks every interactive element on the all-visits list as the QA
// test user.
//
// Page layout (from src/app/visits/page.tsx):
//   - PageHeader with "+ New visit" Link  → outbound (/visits/new)
//   - FilterBar — 5 `<Link>` pills (all / ready / review / signed /
//     processing) each with `?filter=` URL param. The page is a server
//     component, so each pill click triggers a server-rendered re-fetch
//     via Next's RSC GET. clickAndClassify only watches non-GET
//     responses, so the expected classification is VISUAL_ONLY (DOM
//     swaps in for the new filter slice) or NO_NETWORK_FIRED (when the
//     swap finishes before the settle window). Either is fine — the
//     critical assertion is "no DB write to transcribe_visits".
//   - VisitList rows — each is `<Link href="/visits/{id}">`. Outbound;
//     enumerate but never click (would leave the page).
//   - AppFrame chrome:
//       · Sidebar nav rows (Dashboard / Visits / Patients / Settings)
//       · Top-bar: brand → /dashboard, Cmd-K palette button (in-page),
//         "+ New visit" link (outbound), avatar dropdown trigger.
//
// Per filter-pill click: snapshot transcribe_visits BEFORE/AFTER, plus
// URL before/after, and emit a `filter-pill` event with
// `{ pill, urlBefore, urlAfter, urlChanged, dbChanged }`. Any DB write
// is a finding (filter must be read-only).
//
// Auth via lib/walker-base.mjs getOrCreateAuthState (session reuse —
// no per-walker login). Same /login-redirect retry shape as
// sweep-visit-page.mjs / sweep-dashboard.mjs.
//
// Usage:
//   node sweep-visits-list.mjs                  # default /visits
//   node sweep-visits-list.mjs --skip-clicks    # enumerate-only
//   node sweep-visits-list.mjs --filter ready   # land on ?filter=ready
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
    filter: null,
    timeout: 15_000,
  };
  for (let i = 2; i < args.length; i += 1) {
    const a = args[i];
    if (a === '--base') { opts.base = args[i + 1]; i += 1; }
    else if (a === '--filter') { opts.filter = args[i + 1]; i += 1; }
    else if (a === '--skip-clicks') { opts.skipClicks = true; }
    else if (a === '--timeout') { opts.timeout = Number(args[i + 1]); i += 1; }
    else if (a === '--help' || a === '-h') {
      stderr.write(
        'sweep-visits-list.mjs [--filter all|ready|review|signed|processing] [--skip-clicks] [--timeout ms]\n'
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
const TARGET_URL = opts.filter ? `/visits?filter=${opts.filter}` : '/visits';

// The 5 filter pills — these are the in-page click targets we care
// about. Matching by visible text is fine: each label is unique within
// the FilterBar and the chips are .qm-lin-pill / .qm-lin-pill--sage so
// `getByRole('link', { name })` resolves them unambiguously.
const FILTER_PILLS = [
  { id: 'all', label: 'All' },
  { id: 'ready', label: 'Ready' },
  { id: 'review', label: 'Needs review' },
  { id: 'signed', label: 'Signed' },
  { id: 'processing', label: 'Processing' },
];

// ---------------------------------------------------------------------------
// DOM enumeration — same shape as sweep-visit-page.mjs / sweep-dashboard.mjs.
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

/** Decide whether an element's click would leave /visits. The 5 filter
 *  pills are `<Link href="/visits[?filter=...]">` — they stay in-page.
 *  Everything else with a different href prefix is outbound (visit row
 *  links → /visits/{id}, "+ New visit" → /visits/new, sidebar →
 *  /dashboard, /patients, /settings, etc.). Buttons without href are
 *  presumed in-page (Cmd-K, avatar dropdown). */
function isOutbound(el) {
  if (el.tag !== 'a') return false;
  if (!el.href) return false;
  // Same-page filter pills: bare /visits or /visits?filter=... query.
  if (el.href === '/visits') return false;
  if (el.href.startsWith('/visits?')) return false;
  if (el.href.startsWith('/visits#')) return false;
  // Everything else — including /visits/{id} row links — is outbound.
  return true;
}

/** Identify a filter pill by enumerated element. Returns the pill id
 *  (one of FILTER_PILLS[].id) or null. */
function pillIdFor(el) {
  if (el.tag !== 'a') return null;
  if (el.href === '/visits') return 'all';
  if (!el.href || !el.href.startsWith('/visits?filter=')) return null;
  const m = el.href.match(/[?&]filter=([^&]+)/);
  return m ? m[1] : null;
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
      name: 'visits-list',
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

    // Baseline audit count. /visits writes one VIEWED_VISIT_LIST audit
    // row per server render (Round 3 PR-C, A05-P0-004). The walker
    // captures the unscoped recent count — each subsequent filter-pill
    // click should ADD one VIEWED_VISIT_LIST row (because the page
    // re-renders as an RSC), but should NOT touch transcribe_visits.
    const auditBaseline = snapshotAuditCount(null);
    emit({
      event: 'audit-baseline',
      url: TARGET_URL,
      count: auditBaseline,
      expected: ['VIEWED_VISIT_LIST'],
    });

    const elements = await enumerate(page);
    counters.elements = elements.length;
    for (const el of elements) {
      emit({ event: 'element', ...el });
    }

    if (!opts.skipClicks) {
      // Filter clicks must NEVER mutate transcribe_visits — any diff is
      // a finding. We snapshot the 5 most-recently-touched rows and
      // diff them across the click. The audit-log delta is computed
      // separately via snapshotAuditCount(null).
      const dbSnapshotSpec = [
        {
          table: 'transcribe_visits',
          where: 'TRUE ORDER BY "updatedAt" DESC LIMIT 5',
        },
      ];

      for (const el of elements) {
        if (el.disabled) {
          emit({ event: 'click-skipped', label: el.text, reason: 'disabled' });
          continue;
        }
        // Visit row links + "+ New visit" + sidebar nav = outbound.
        // Enumerate but don't click (would leave the page).
        if (isOutbound(el)) {
          emit({
            event: 'click-skipped',
            label: el.text,
            reason: 'leaves-page',
            href: el.href,
          });
          continue;
        }

        // In-page click targets remaining after the filter:
        //   - 5 filter pills (Link, href=/visits[?filter=...])
        //   - Top-bar Cmd-K palette <button> (no href, in-page)
        //   - Top-bar avatar dropdown trigger <button> (no href)
        //   - Top-bar QuillMD brand Link (href=/dashboard) — caught by
        //     isOutbound above.

        const pill = pillIdFor(el);
        const isFilterPill = pill !== null;

        // For filter pills, capture URL before/after so we can confirm
        // the navigation lands on the correct ?filter= slice without
        // a DB write. For non-pill in-page clicks (Cmd-K, avatar), use
        // the same shape as sweep-dashboard.mjs.
        const urlBefore = page.url();

        // F-16 closure: prefer href-based locators for filter pills
        // (and any other anchor with a stable href). Visible text is
        // a fragile selector — renaming "All" → "Show all" would
        // silently break the walker. The href is the contract; the
        // label is decoration.
        let selectorSpec;
        if (isFilterPill) {
          // Pin by exact href — `/visits` for the all pill, otherwise
          // `/visits?filter=<id>`. CSS attribute selector is what
          // Playwright resolves cheapest.
          selectorSpec = `a[href="${el.href}"]`;
        } else if (el.ariaLabel) {
          selectorSpec = {
            role: el.role ?? (el.tag === 'a' ? 'link' : 'button'),
            name: el.ariaLabel,
          };
        } else {
          selectorSpec = { text: el.text || '?', exact: false };
        }

        const result = await clickAndClassify(page, {
          name: el.text || el.ariaLabel || `(${el.tag})`,
          selector: selectorSpec,
          dbSnapshotSpec,
          auditTargetId: null,
          settleMs: 800,
        });
        counters.clicks += 1;

        const urlAfter = page.url();
        const urlChanged = urlBefore !== urlAfter;

        if (isFilterPill) {
          // Filter-pill specific event — captures the read-only
          // assertion shape the spec calls out.
          emit({
            event: 'filter-pill',
            pill,
            label: el.text,
            urlBefore,
            urlAfter,
            urlChanged,
            dbChanged: result.dbChanged,
            classification: result.classification,
          });
          // A DB write during a filter-pill click is a hard finding —
          // the filter is supposed to be a server-rendered read-only
          // slice. clickAndClassify already reports it via dbChanged;
          // we tally it here so counters.findings reflects it.
          if (result.dbChanged) {
            counters.findings += 1;
          }
        }

        if (
          result.classification === 'PRETEND_SUCCESS_FALLBACK' ||
          result.classification === 'CLICK_THREW' ||
          (typeof result.classification === 'string' &&
            result.classification.startsWith('HTTP_5'))
        ) {
          counters.findings += 1;
        }
        // Note: for filter pills, NO_NETWORK_FIRED and VISUAL_ONLY are
        // both expected (RSC GET re-fetch is hidden from
        // clickAndClassify, which only watches non-GET responses), so
        // we deliberately do NOT count those toward findings here.
        // For non-pill in-page clicks (Cmd-K, avatar) the same
        // classifications still surface via the per-click record so
        // a Lead reviewing NDJSON can spot orphan dispatchers.

        emit({ event: 'click', label: el.text, isFilterPill, ...result });

        // Re-navigate after each click for a stable starting state —
        // filter clicks change the URL, so the next iteration would
        // otherwise start from `?filter=<previous>` and the pill we
        // try to click next might be the active one (different DOM).
        await page.goto(TARGET_URL, {
          waitUntil: 'networkidle',
          timeout: opts.timeout,
        });
      }
    }

    emit({ event: 'sweep-end', ...counters });
    // Shape-consistency emit so sweep-all.mjs's table picks this
    // walker up as OK rather than mis-categorising "completed with
    // findings" as WARN. Findings are surfaced via the per-click
    // records and the counters.findings tally — they don't downgrade
    // the walker itself.
    emit({
      event: 'walker-result',
      name: 'visits-list',
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
      name: 'visits-list',
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
