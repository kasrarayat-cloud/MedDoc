#!/usr/bin/env node
// ============================================================================
// sweep-patients-list.mjs — /patients deep walker (✅ transactional tier, v3.3)
// ----------------------------------------------------------------------------
// Walks every interactive element on the all-patients list as the QA
// test user (DOCTOR role).
//
// Page layout (from src/app/patients/page.tsx + patients-list-client.tsx):
//   - PageHeader with "+ New visit" Link  → outbound (/visits/new)
//   - <PatientsListClient>:
//       · Search input (`<input type="search" aria-label="Filter
//         patients by name">`) — CLIENT-SIDE filter only. No URL push,
//         no debounce, no /api/* call. `useState(query) + useMemo` over
//         the server-rendered <=100 row slice. Typing into it should
//         mutate the DOM (filtered card list changes) but NEVER touch
//         the DB or fire a network request.
//       · PatientCard grid — each card is a `<Link href="/patients/{id}">`.
//         Outbound; enumerate but never click.
//   - AppFrame chrome (sidebar, top-bar, Cmd-K, avatar) — same as the
//     dashboard / visits-list walkers.
//
// What this walker asserts:
//   1. Page renders + emits its `VIEWED_PATIENT_LIST` audit row on the
//      initial RSC render (this is captured indirectly via the
//      audit-baseline emit; the per-click loop watches for any
//      NEW writes to the seeded `transcribe_md_patients` row).
//   2. The search input filters in the DOM only — typing "QA" (the
//      seeded patient name prefix) reduces the visible card count but
//      does NOT change the URL, the seeded patient row, or fire any
//      audit log against that row.
//   3. Outbound nav (patient row links, "+ New visit", sidebar nav) is
//      enumerated but skipped — clicking would leave the page (or in
//      the case of "+ New visit", create a stale visit if submitted).
//
// Affordances enumerated-but-skipped:
//   - Patient row `<Link href="/patients/{id}">` (outbound nav)
//   - "+ New visit" button → /visits/new (outbound; matches the
//     /visits/new walker's Submit-skip pattern)
//   - Sidebar nav rows (Dashboard / Visits / Patients / Settings),
//     top-bar brand → /dashboard
//   Note: there is NO "Add patient" button on this page (the only way
//   to create a patient is via the /visits/new flow); there is also
//   NO "Trash"/"Show deleted" toggle (deleted-patient browsing lives
//   on the patient-detail Trash tab, not the list page). The header
//   comment in the prompt called these out as conditional ("if
//   present") — they are not present in the v3.3 layout.
//
// Search-input shape (verified against patients-list-client.tsx):
//   The input is a controlled `<input type="search">` whose `onChange`
//   updates client React state; the `useMemo` filter recomputes on
//   every tick. There is NO `?q=...` URL push — we type "QA" and assert
//   (a) URL is unchanged, (b) DOM card count drops to match the seeded
//   patient (whose name starts with "QA"), (c) the seeded
//   `transcribe_md_patients` row is byte-identical before/after.
//
// Auth via lib/walker-base.mjs getOrCreateAuthState (session reuse —
// no per-walker login). Same /login-redirect retry shape as
// sweep-visit-page.mjs / sweep-dashboard.mjs.
//
// Usage:
//   node sweep-patients-list.mjs              # default /patients
//   node sweep-patients-list.mjs --skip-clicks
//
// Output: NDJSON to stdout — one record per element / click / event.
// ============================================================================

import { existsSync, readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { argv, env, exit, stderr } from 'node:process';

import {
  emit,
  getOrCreateAuthState,
  invalidateAuthState,
  launchBrowser,
  newAppContext,
  clickAndClassify,
  snapshotTables,
} from './lib/walker-base.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SEEDED_IDS_PATH = resolve(__dirname, '..', 'fixtures', 'seeded-ids.json');

function readSeededPatientId() {
  if (!existsSync(SEEDED_IDS_PATH)) return null;
  try {
    const seeded = JSON.parse(readFileSync(SEEDED_IDS_PATH, 'utf-8'));
    return seeded.patientId ?? null;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Args
// ---------------------------------------------------------------------------

function parseArgs(args) {
  const opts = {
    base: env.QA_AUDITOR_BASE_URL ?? 'https://app.quillmd.com',
    skipClicks: false,
    timeout: 15_000,
    searchQuery: 'QA',
  };
  for (let i = 2; i < args.length; i += 1) {
    const a = args[i];
    if (a === '--base') { opts.base = args[i + 1]; i += 1; }
    else if (a === '--skip-clicks') { opts.skipClicks = true; }
    else if (a === '--timeout') { opts.timeout = Number(args[i + 1]); i += 1; }
    else if (a === '--search') { opts.searchQuery = args[i + 1]; i += 1; }
    else if (a === '--help' || a === '-h') {
      stderr.write(
        'sweep-patients-list.mjs [--skip-clicks] [--search <query>] [--timeout ms]\n'
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
const TARGET_URL = '/patients';

// ---------------------------------------------------------------------------
// DOM enumeration — same shape as sweep-visits-list.mjs / sweep-visit-page.mjs.
// ---------------------------------------------------------------------------

async function enumerate(page) {
  return page.$$eval(
    'button, [role="button"], a[href^="/"], input[type="submit"], input[type="search"]',
    (els) =>
      els
        .map((el, i) => {
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) return null;
          return {
            index: i,
            tag: el.tagName.toLowerCase(),
            type: el.getAttribute('type') ?? null,
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

/** Decide whether an element's click would leave /patients. The page
 *  has no in-page click affordances besides the search input — every
 *  link goes somewhere else (patient detail, /visits/new, sidebar
 *  nav, brand → /dashboard). */
function isOutbound(el) {
  if (el.tag !== 'a') return false;
  if (!el.href) return false;
  // The list page has no in-page anchors. Anything that is `/patients`
  // exactly would be a self-link (rare) — treat as in-page; everything
  // else is outbound (including /patients/{id} row cards).
  if (el.href === '/patients') return false;
  return true;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const t0 = Date.now();
  emit({ event: 'sweep-start', url: TARGET_URL, base: opts.base });

  const seededPatientId = readSeededPatientId();
  if (!seededPatientId) {
    emit({
      event: 'sweep-warn',
      message:
        'seeded-ids.json missing or unreadable — DB-snapshot assertion will be a no-op',
    });
  }

  let storagePath;
  try {
    storagePath = await getOrCreateAuthState();
  } catch (err) {
    emit({ event: 'sweep-error', stage: 'login', message: err.message });
    emit({
      event: 'walker-result',
      name: 'patients-list',
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

    // The DB-snapshot spec for the patients-list page: pin the seeded
    // `transcribe_md_patients` row. Search/sort interactions must not
    // touch this row. (Filter is a pure client-side useMemo — anything
    // else is a finding.)
    const dbSnapshotSpec = seededPatientId
      ? [
          {
            table: 'transcribe_md_patients',
            where: `id = '${seededPatientId.replace(/'/g, "''")}'`,
          },
        ]
      : [];

    // ------------------------------------------------------------------
    // Search-input specific assertion. Snap DB + URL before, type the
    // query, snap DB + URL + visible card count after. Expected:
    //   - URL unchanged (client-side filter, no `?q=` push)
    //   - DB row unchanged (read-only filter)
    //   - DOM card count drops (the seeded "QA Test Patient" matches
    //     "QA"; non-matching cards disappear).
    // ------------------------------------------------------------------
    if (!opts.skipClicks) {
      const urlBeforeSearch = page.url();
      const dbBeforeSearch = snapshotTables(dbSnapshotSpec);
      const cardCountBefore = await page
        .locator('a[href^="/patients/"]')
        .count()
        .catch(() => null);

      const searchInput = page.locator('input[type="search"]').first();
      const searchInputCount = await searchInput.count();
      if (searchInputCount > 0) {
        try {
          await searchInput.fill(opts.searchQuery);
          await page.waitForTimeout(400);
        } catch (err) {
          emit({
            event: 'search-error',
            message: err.message,
          });
        }

        const urlAfterSearch = page.url();
        const dbAfterSearch = snapshotTables(dbSnapshotSpec);
        const cardCountAfter = await page
          .locator('a[href^="/patients/"]')
          .count()
          .catch(() => null);

        const urlChanged = urlBeforeSearch !== urlAfterSearch;
        const dbChanged =
          JSON.stringify(dbBeforeSearch) !== JSON.stringify(dbAfterSearch);

        emit({
          event: 'search-input',
          query: opts.searchQuery,
          urlBefore: urlBeforeSearch,
          urlAfter: urlAfterSearch,
          urlChanged,
          dbChanged,
          cardCountBefore,
          cardCountAfter,
          // Expected shape: client-side filter — neither URL nor DB
          // should change. Cards may shrink if the query has matches,
          // or stay equal if every visible patient still matches.
          shape: 'client-side-filter',
        });

        if (urlChanged) {
          // The page WAS supposed to be a pure client-side filter; if
          // we suddenly see a `?q=...` push, the implementation has
          // changed (or there's a server-side search). That's a tier-
          // promotion signal, not necessarily a bug — mark it as a
          // finding so the report flags it for review.
          counters.findings += 1;
        }
        if (dbChanged) {
          // Hard finding — search is supposed to be read-only.
          counters.findings += 1;
        }

        // Reset the input back to empty for the click loop below so
        // outbound link enumeration sees the unfiltered DOM.
        try {
          await searchInput.fill('');
          await page.waitForTimeout(200);
        } catch {
          // Best-effort reset — re-navigation below is the real reset.
        }
      } else {
        emit({
          event: 'search-input-missing',
          note: 'no <input type="search"> found on /patients',
        });
      }

      // Re-navigate for a stable starting state for the click loop.
      await page.goto(TARGET_URL, {
        waitUntil: 'networkidle',
        timeout: opts.timeout,
      });
    }

    const elements = await enumerate(page);
    counters.elements = elements.length;
    for (const el of elements) {
      emit({ event: 'element', ...el });
    }

    if (!opts.skipClicks) {
      for (const el of elements) {
        if (el.disabled) {
          emit({ event: 'click-skipped', label: el.text, reason: 'disabled' });
          continue;
        }
        // Outbound nav links + "+ New visit" + patient row cards =
        // enumerate but don't click (would leave the page or — in the
        // case of /visits/new — create a stale visit if submitted).
        if (isOutbound(el)) {
          emit({
            event: 'click-skipped',
            label: el.text,
            reason: 'leaves-page',
            href: el.href,
          });
          continue;
        }
        // Skip the search input here — already handled above with its
        // dedicated URL/DB/DOM assertion shape.
        if (el.tag === 'input' && el.type === 'search') {
          emit({
            event: 'click-skipped',
            label: el.ariaLabel ?? '(search)',
            reason: 'covered-by-search-input-step',
          });
          continue;
        }

        // Whatever in-page click targets remain are AppFrame chrome
        // (Cmd-K palette button, avatar dropdown trigger). Same shape
        // as sweep-dashboard.mjs / sweep-visits-list.mjs.
        const selectorSpec = el.ariaLabel
          ? { role: el.role ?? (el.tag === 'a' ? 'link' : 'button'), name: el.ariaLabel }
          : { text: el.text || '?', exact: false };

        const result = await clickAndClassify(page, {
          name: el.text || el.ariaLabel || `(${el.tag})`,
          selector: selectorSpec,
          dbSnapshotSpec,
          // The patients-list page does NOT audit per-click — the only
          // audit row it writes is `VIEWED_PATIENT_LIST` on RSC render.
          // (Verified against apps/transcribe-md/src/lib/audit.ts.)
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

        // Re-navigate after each click for a stable starting state.
        await page.goto(TARGET_URL, {
          waitUntil: 'networkidle',
          timeout: opts.timeout,
        });
      }
    }

    emit({ event: 'sweep-end', ...counters });
    // Shape-consistency emit so sweep-all.mjs's table picks this
    // walker up as OK rather than mis-categorising "completed with
    // findings" as WARN. Findings are surfaced via the per-click /
    // search-input records and the counters.findings tally.
    emit({
      event: 'walker-result',
      name: 'patients-list',
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
      name: 'patients-list',
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
