#!/usr/bin/env node
// ============================================================================
// sweep-patient-detail.mjs — /patients/[id] deep walker (✅ tier, v3.2)
// ----------------------------------------------------------------------------
// Walks every interactive element on the patient detail page as the QA
// test user.
//
// Page layout (from src/app/patients/[id]/page.tsx):
//   - Breadcrumb: "Patients › {name}" (link → /patients, outbound)
//   - PatientHeaderCard:
//       · Avatar + name + DOB / MRN / external-id / insurance
//       · Problem-list chips (read-only) + [Manage] button
//         (ProblemListDialog trigger — opens a Radix Dialog;
//         in-page DOM mutation, not navigation)
//       · "+ New visit" Link → /visits/new?patientId=...   (outbound)
//       · "Export" anchor → /api/patients/{id}/export       (outbound)
//       · [Edit] button (EditPatientDialog trigger — in-page dialog)
//       · [Delete patient] button (DeletePatientDialog trigger —
//         in-page dialog)
//   - Four StatCards (read-only, no clickables)
//   - TabBar (Visits / Notes / Files / Trash):
//       · Each tab is `<Link href="/patients/{id}[?tab=...]">` with
//         `scroll={false}`. Server re-renders with the new ?tab= slice;
//         in-page from the walker's POV (URL changes, page does not).
//       · Trash tab is conditionally rendered: trashCount === 0 → not
//         in DOM. Walker checks for absence and skips gracefully.
//   - Visits tab content: <VisitList> rows — each row is a
//     `<Link href="/visits/{id}">`. OUTBOUND; enumerate but never
//     click (would leave the page).
//   - Notes tab: <StubTab title="Notes" body="A freeform clinical
//     notepad ... Coming soon">. INTENTIONAL stub copy — NOT a
//     pattern-C bug. The walker emits a `tab-content` event with the
//     observed copy so reports can verify the stub didn't silently
//     change.
//   - Files tab: <StubTab title="Files" body="Patient-attached files
//     ... Coming soon">. SAME — intentional stub.
//   - Trash tab (when present): grid of <TrashedVisitCard> components,
//     each card has its own Restore / Delete-permanently buttons that
//     mutate transcribe_visits. THOSE BUTTONS ARE OUT OF SCOPE for
//     the v3.2 walker — clicking Restore would leave the patient with
//     a different active/trash count and pollute fixtures. We
//     enumerate them but never click; restore tests live in a future
//     sweep-trash-restore walker.
//   - AppFrame chrome (sidebar + topnav): same as sweep-dashboard.mjs
//     — sidebar nav rows / brand / Cmd-K palette / avatar. Sidebar
//     nav rows are outbound; Cmd-K + avatar are in-page.
//
// Per click target: snapshot transcribe_md_patients (read-scoping
// check — the patient row should NEVER mutate from view-only clicks
// or tab switches) + transcribe_visits (sanity for tab clicks). Audit
// delta is computed unscoped (auditTargetId=null) — every tab switch
// is an RSC re-render that emits a fresh VIEWED_PATIENT_FILE row, so
// audit-delta > 0 is EXPECTED for tab clicks (and is logged on the
// per-click record but doesn't downgrade the walker).
//
// Expected audits (Round 3 PR-C):
//   - On load:        VIEWED_PATIENT_FILE (one row per RSC render)
//   - Per tab click:  one additional VIEWED_PATIENT_FILE row
//   - On Visits tab:  no VIEWED_VISIT* rows from this page (those
//     fire only when /visits/[id] is opened, which we don't click)
//
// Auth via lib/walker-base.mjs getOrCreateAuthState (session reuse —
// no per-walker login). Same /login-redirect retry shape as
// sweep-visit-page.mjs / sweep-dashboard.mjs / sweep-visits-list.mjs.
//
// Constraints (from the spec):
//   - Do NOT click visit-row links inside the Visits tab (would leave
//     the page). Treated as outbound.
//   - Do NOT click the Trash tab if it's not in the DOM (no trash
//     items — zero-trash patients render the tab as `hidden`).
//   - Do NOT submit any form (Edit / Delete / Problem-list dialogs).
//     Triggers may be clicked (open the dialog → DOM mutates) but no
//     submit click follows.
//
// Usage:
//   node sweep-patient-detail.mjs                      # default — seeded patient
//   node sweep-patient-detail.mjs --patient-id <id>    # override
//   node sweep-patient-detail.mjs --tab notes          # land on ?tab=notes
//   node sweep-patient-detail.mjs --skip-clicks        # enumerate-only
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
  snapshotAuditCount,
} from './lib/walker-base.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SEEDED_IDS_PATH = resolve(__dirname, '..', 'fixtures', 'seeded-ids.json');

// ---------------------------------------------------------------------------
// Args
// ---------------------------------------------------------------------------

function parseArgs(args) {
  const opts = {
    base: env.QA_AUDITOR_BASE_URL ?? 'https://app.quillmd.com',
    patientId: null,
    tab: null,
    skipClicks: false,
    timeout: 15_000,
  };
  for (let i = 2; i < args.length; i += 1) {
    const a = args[i];
    if (a === '--base') { opts.base = args[i + 1]; i += 1; }
    else if (a === '--patient-id') { opts.patientId = args[i + 1]; i += 1; }
    else if (a === '--tab') { opts.tab = args[i + 1]; i += 1; }
    else if (a === '--skip-clicks') { opts.skipClicks = true; }
    else if (a === '--timeout') { opts.timeout = Number(args[i + 1]); i += 1; }
    else if (a === '--help' || a === '-h') {
      stderr.write(
        'sweep-patient-detail.mjs [--patient-id <id>] [--tab notes|files|trash] [--skip-clicks] [--timeout ms]\n'
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

// ---------------------------------------------------------------------------
// Fixture resolution. Seeded fixtures path:
// fixtures/seeded-ids.json. The walker is a no-op (walker-skip event,
// clean exit) when the file is missing — same shape as the v2 stub.
// ---------------------------------------------------------------------------

function resolvePatientId() {
  if (opts.patientId) return opts.patientId;
  if (!existsSync(SEEDED_IDS_PATH)) return null;
  try {
    const seeded = JSON.parse(readFileSync(SEEDED_IDS_PATH, 'utf-8'));
    return seeded.patientId ?? null;
  } catch {
    return null;
  }
}

const PATIENT_ID = resolvePatientId();
if (!PATIENT_ID) {
  emit({
    event: 'walker-skip',
    name: 'patient-detail',
    reason:
      'seeded patient id missing — run apps/transcribe-md/scripts/seed-qa-fixtures.ts',
  });
  emit({
    event: 'walker-result',
    name: 'patient-detail',
    url: null,
    ok: true,
    skipped: true,
  });
  exit(0);
}

const TARGET_URL = opts.tab
  ? `/patients/${PATIENT_ID}?tab=${opts.tab}`
  : `/patients/${PATIENT_ID}`;

// ---------------------------------------------------------------------------
// DOM enumeration — same shape as sweep-visit-page.mjs / sweep-dashboard.mjs.
// ---------------------------------------------------------------------------

async function enumerate(page) {
  return page.$$eval(
    'button, [role="button"], a[href^="/"], a[href^="/api/"], input[type="submit"]',
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
            type: el.getAttribute('type') ?? null,
          };
        })
        .filter(Boolean)
  );
}

const BASE_URL = `/patients/${PATIENT_ID}`;

/** Decide whether an element's click would leave /patients/[id]. The 4
 *  tab links (`/patients/{id}[?tab=...]`) stay in-page — they're the
 *  whole point of the deep walk. Everything else with a different
 *  href prefix is outbound (visit row links, "+ New visit",
 *  /api/patients/{id}/export, sidebar nav rows, breadcrumb). Buttons
 *  without href are presumed in-page (Cmd-K, avatar dropdown, dialog
 *  triggers). */
function isOutbound(el) {
  if (el.tag !== 'a') return false;
  if (!el.href) return false;
  // Same-page tab links: bare /patients/{id} or /patients/{id}?...
  if (el.href === BASE_URL) return false;
  if (el.href.startsWith(`${BASE_URL}?`)) return false;
  if (el.href.startsWith(`${BASE_URL}#`)) return false;
  return true;
}

/** Identify a tab link by enumerated element. Returns one of
 *  'visits' | 'notes' | 'files' | 'trash' or null. */
function tabIdFor(el) {
  if (el.tag !== 'a' || !el.href) return null;
  if (el.href === BASE_URL) return 'visits';
  if (!el.href.startsWith(`${BASE_URL}?`)) return null;
  const m = el.href.match(/[?&]tab=([^&]+)/);
  if (!m) return null;
  if (['notes', 'files', 'trash'].includes(m[1])) return m[1];
  return null;
}

/** Decide whether a button is a Restore / Delete-permanently action
 *  on a TrashedVisitCard. We never click those — they'd mutate
 *  transcribe_visits and pollute the fixture's active/trash split. */
function isTrashedVisitMutator(el) {
  if (el.tag !== 'button' && el.role !== 'button') return false;
  const t = (el.text || '').toLowerCase();
  return (
    t.includes('restore') ||
    t.includes('permanently') ||
    t.includes('delete forever')
  );
}

/** Decide whether a button is a dialog-submit (inside Edit / Delete /
 *  Problem-list dialogs). Triggers are fine to click (open the
 *  dialog), but submits are out of scope per the no-form-submit
 *  constraint. We rely on text matching as a coarse filter — the
 *  trigger text is "Edit", "Delete patient", "Manage" while submit
 *  text is "Save" / "Save changes" / "Confirm delete" / "Apply".
 *  When in doubt, the type=submit attribute is a hard skip. */
function isDialogSubmit(el) {
  if (el.type === 'submit') return true;
  const t = (el.text || '').toLowerCase();
  return (
    t === 'save' ||
    t === 'save changes' ||
    t === 'confirm delete' ||
    t === 'delete patient' ||
    t.startsWith('apply') ||
    t.startsWith('confirm') ||
    t.startsWith('save ')
  );
}

// ---------------------------------------------------------------------------
// Snapshot helpers
// ---------------------------------------------------------------------------

/** Capture the visible stub-tab copy after navigating to ?tab=notes
 *  or ?tab=files. The copy is intentional (StubTab component in
 *  page.tsx) — the agent emits it so the report can prove the
 *  empty-state didn't regress to e.g. blank or an error. */
async function captureStubCopy(page) {
  return page.evaluate(() => {
    // StubTab renders: title kicker + "Coming soon" h2 + body <p>.
    // Anchor by the literal "Coming soon" h2 since that's stable
    // across both stubs and unique on the page.
    const h2 = Array.from(document.querySelectorAll('h2')).find(
      (n) => n.textContent?.trim().toLowerCase() === 'coming soon'
    );
    if (!h2) return null;
    const container = h2.parentElement;
    if (!container) return null;
    const kickerEl = container.querySelector('div');
    const bodyEl = container.querySelector('p');
    return {
      kicker: (kickerEl?.textContent ?? '').trim(),
      heading: (h2.textContent ?? '').trim(),
      body: (bodyEl?.textContent ?? '').trim(),
    };
  });
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const t0 = Date.now();
  emit({
    event: 'sweep-start',
    url: TARGET_URL,
    base: opts.base,
    patientId: PATIENT_ID,
  });

  let storagePath;
  try {
    storagePath = await getOrCreateAuthState();
  } catch (err) {
    emit({ event: 'sweep-error', stage: 'login', message: err.message });
    emit({
      event: 'walker-result',
      name: 'patient-detail',
      url: TARGET_URL,
      ok: false,
      loadErr: err.message,
      stage: 'login',
    });
    exit(1);
  }

  const browser = await launchBrowser();
  let exitCode = 0;
  const counters = {
    elements: 0,
    clicks: 0,
    findings: 0,
    tabsWalked: 0,
    trashTabPresent: 0,
  };

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

    // Baseline audit count. /patients/[id] writes one VIEWED_PATIENT_FILE
    // audit row per server render (Round 3 PR-C, A05-P0-004). The walker
    // captures the unscoped recent count — each subsequent tab click
    // should ADD one VIEWED_PATIENT_FILE row (RSC re-render with new
    // ?tab= slice), but should NOT touch transcribe_md_patients.
    const auditBaseline = snapshotAuditCount(null);
    emit({
      event: 'audit-baseline',
      url: TARGET_URL,
      count: auditBaseline,
      expected: ['VIEWED_PATIENT_FILE'],
      note: 'Round 3 PR-C — VIEWED_PATIENT_FILE fires once per RSC render of /patients/[id]',
    });

    // Trash-tab presence check. The Trash tab is rendered ONLY when
    // trashCount > 0 (page.tsx :478 — `hidden: trashCount === 0`).
    // We probe the DOM rather than querying the DB so the walker is
    // self-contained. This drives the spec's "Trash tab only renders
    // when items exist — check the DOM + skip if absent" guidance.
    const trashTabPresent = await page
      .locator('a[href*="tab=trash"]')
      .count()
      .catch(() => 0);
    counters.trashTabPresent = trashTabPresent;
    emit({
      event: 'trash-tab-presence',
      present: trashTabPresent > 0,
      note:
        trashTabPresent > 0
          ? 'patient has trashed visits — tab will be walked'
          : 'no trashed visits for this patient — Trash tab absent (expected)',
    });

    const elements = await enumerate(page);
    counters.elements = elements.length;
    for (const el of elements) {
      emit({ event: 'element', ...el });
    }

    if (!opts.skipClicks) {
      // /patients/[id] view-only clicks (tabs, dialog triggers,
      // sidebar) should NEVER mutate either of these tables. The
      // patient row in particular is the canary: a write here would
      // mean a tab click is doing something it shouldn't (Round 3
      // read-scoping check). transcribe_visits is captured to detect
      // accidental Trash-tab restore mutations.
      const dbSnapshotSpec = [
        {
          table: 'transcribe_md_patients',
          where: `id = '${PATIENT_ID.replace(/'/g, "''")}'`,
        },
        {
          table: 'transcribe_visits',
          where: `"patientId" = '${PATIENT_ID.replace(/'/g, "''")}' ORDER BY "updatedAt" DESC LIMIT 5`,
        },
      ];

      for (const el of elements) {
        if (el.disabled) {
          emit({ event: 'click-skipped', label: el.text, reason: 'disabled' });
          continue;
        }
        // Visit row links + sidebar nav + Export anchor + "+ New visit"
        // + breadcrumb-back-to-/patients = outbound. Enumerate but
        // don't click (would leave the page).
        if (isOutbound(el)) {
          emit({
            event: 'click-skipped',
            label: el.text,
            reason: 'leaves-page',
            href: el.href,
          });
          continue;
        }
        // Trash card mutator buttons: never click. They'd shift the
        // active/trash split for the seeded patient.
        if (isTrashedVisitMutator(el)) {
          emit({
            event: 'click-skipped',
            label: el.text,
            reason: 'trashed-visit-mutator',
          });
          continue;
        }
        // Dialog-submit buttons inside open dialogs: never click —
        // the spec forbids form submissions on this page.
        if (isDialogSubmit(el)) {
          emit({
            event: 'click-skipped',
            label: el.text,
            reason: 'dialog-submit',
          });
          continue;
        }

        // In-page click targets remaining after the filter:
        //   - 3 (or 4, when Trash present) tab Links
        //   - Edit / Delete / Manage dialog trigger <button>s
        //   - Top-bar Cmd-K palette <button>
        //   - Top-bar avatar dropdown trigger <button>

        const tabId = tabIdFor(el);
        const isTab = tabId !== null;
        const urlBefore = page.url();

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

        const urlAfter = page.url();
        const urlChanged = urlBefore !== urlAfter;

        if (isTab) {
          counters.tabsWalked += 1;
          // Capture the rendered tab content snippet so reports can
          // verify the stub copy (Notes / Files) matches the
          // intentional empty-state. Visits / Trash tabs render
          // structured grids — capture is null for those.
          let tabContent = null;
          if (tabId === 'notes' || tabId === 'files') {
            tabContent = await captureStubCopy(page).catch(() => null);
          }
          emit({
            event: 'tab-content',
            tab: tabId,
            label: el.text,
            urlBefore,
            urlAfter,
            urlChanged,
            classification: result.classification,
            dbChanged: result.dbChanged,
            stubCopy: tabContent,
            // Reminder for the report: the Notes + Files tab copy
            // ("Coming soon" + body) is INTENTIONAL — page.tsx renders
            // <StubTab> with hand-typed copy. NOT a Pattern C orphan.
            stubIsIntentional: tabId === 'notes' || tabId === 'files',
          });
          // A patient-row write during a tab click is a hard finding
          // (Round 3 read-scoping). Tally it explicitly so
          // counters.findings reflects it.
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
        // Note: NO_NETWORK_FIRED + VISUAL_ONLY are EXPECTED for tab
        // clicks (RSC GET re-fetch is hidden from clickAndClassify,
        // which only watches non-GET responses) and for dialog
        // triggers (Radix Dialog mutates DOM without firing a
        // network request). We surface them in the per-click record
        // but don't count them toward findings here — same posture
        // as sweep-visits-list.mjs's filter pills.

        emit({ event: 'click', label: el.text, isTab, ...result });

        // Re-navigate after each click for a stable starting state.
        // Tab clicks change the URL; dialog triggers leave Radix
        // portals + scroll-locks behind that would shadow subsequent
        // locator matches.
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
    // records (with classifications like PRETEND_SUCCESS_FALLBACK)
    // and the counters.findings tally — they don't downgrade the
    // walker itself.
    emit({
      event: 'walker-result',
      name: 'patient-detail',
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
      name: 'patient-detail',
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
