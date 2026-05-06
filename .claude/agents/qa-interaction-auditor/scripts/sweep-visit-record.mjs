#!/usr/bin/env node
// ============================================================================
// sweep-visit-record.mjs — /visits/[id]/record deep walker (✅ tier, v3.3)
// ----------------------------------------------------------------------------
// Walks the live MediaRecorder dictation page as the QA test user. Real
// hardware never opens — getUserMedia + MediaRecorder are stubbed via
// addInitScript before page-load (lib/media-mocks.mjs).
//
// The page lifecycle the walker exercises:
//   1. Land on /visits/<recordDraft-fixture-id>/record (status=QUEUED).
//      Page renders the left-column microphone halo + waveform + status
//      indicator, plus the right-column "listening…" transcript area.
//   2. Click "Start recording". With the mock in place this calls
//      navigator.mediaDevices.getUserMedia (returns a silent stream),
//      constructs MediaRecorder (mock), and transitions UI phase from
//      'idle' → 'requesting' → 'recording'. **No DB write, no network
//      mutation, no audit row.**
//   3. The walker then enumerates clickable affordances on the page
//      after the state transition + classifies each. The "Stop &
//      process" button is visible at this point but the walker
//      explicitly DOES NOT click it — clicking would fire the page's
//      finalizeAndUpload which POSTs an empty blob to
//      /api/visits/[id]/dictation/upload, creating a real (4xx)
//      server-side event outside the read-only walker scope.
//
// Why a deep walker instead of v2 smoke?
//   /visits/[id]/record is the highest-traffic surface in production
//   (every visit lands here once). The v2 smoke skipped it entirely
//   ("needs draft-mode visit + getUserMedia mock"), leaving the most-
//   walked page in the matrix without coverage. v3.3 closes that.
//
// Why not click "Stop & process"?
//   The walker's job is page-load + affordance-enumeration, not end-
//   to-end. A real "Stop" hits /api/.../dictation/upload which would
//   fail with 4xx (empty blob), generate noise in audit_logs, and
//   surface as a PRETEND_SUCCESS_FALLBACK / HTTP_4xx finding the
//   walker would have to explicitly suppress. Cleaner to skip.
//
// Usage:
//   node sweep-visit-record.mjs                       # uses seeded recordDraft fixture
//   node sweep-visit-record.mjs --visit-id <id>       # explicit override
//   node sweep-visit-record.mjs --skip-clicks         # smoke-only
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
} from './lib/walker-base.mjs';
import { MEDIA_MOCK_SCRIPT } from './lib/media-mocks.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SEEDED_IDS_PATH = resolve(__dirname, '..', 'fixtures', 'seeded-ids.json');

function readRecordDraftId() {
  if (!existsSync(SEEDED_IDS_PATH)) return null;
  try {
    const seeded = JSON.parse(readFileSync(SEEDED_IDS_PATH, 'utf-8'));
    return seeded.visitIds?.recordDraft ?? null;
  } catch {
    return null;
  }
}

// ─── argv ──────────────────────────────────────────────────────────────────

function parseArgs(args) {
  const opts = {
    visitId: env.QA_RECORD_DRAFT_VISIT_ID ?? null,
    skipClicks: false,
    timeout: 15_000,
  };
  for (let i = 2; i < args.length; i += 1) {
    const a = args[i];
    if (a === '--visit-id') { opts.visitId = args[i + 1]; i += 1; }
    else if (a === '--skip-clicks') { opts.skipClicks = true; }
    else if (a === '--timeout') { opts.timeout = Number(args[i + 1]); i += 1; }
    else if (a === '--help' || a === '-h') {
      stderr.write(
        'sweep-visit-record.mjs [--visit-id <id>] [--skip-clicks] [--timeout <ms>]\n' +
          '  Reads visitIds.recordDraft from fixtures/seeded-ids.json by default.\n' +
          '  Run apps/transcribe-md/scripts/seed-qa-fixtures.ts to seed the fixture.\n'
      );
      exit(2);
    } else {
      stderr.write(`Unknown arg: ${a}\n`);
      exit(2);
    }
  }
  if (!opts.visitId) {
    opts.visitId = readRecordDraftId();
  }
  return opts;
}

const opts = parseArgs(argv);

// ─── Main ──────────────────────────────────────────────────────────────────

async function main() {
  emit({ event: 'walker-start', name: 'visit-record' });

  if (!opts.visitId) {
    emit({
      event: 'walker-skip',
      name: 'visit-record',
      reason:
        'visitIds.recordDraft missing from fixtures/seeded-ids.json — run apps/transcribe-md/scripts/seed-qa-fixtures.ts first',
    });
    emit({
      event: 'walker-result',
      name: 'visit-record',
      ok: true,
      skipped: true,
    });
    emit({ event: 'walker-end', name: 'visit-record' });
    exit(0);
  }

  const url = `/visits/${opts.visitId}/record`;

  let storagePath;
  try {
    storagePath = await getOrCreateAuthState();
  } catch (err) {
    emit({
      event: 'walker-result',
      name: 'visit-record',
      url,
      ok: false,
      stage: 'login',
      loadErr: err.message,
    });
    emit({ event: 'walker-end', name: 'visit-record' });
    exit(1);
  }

  const browser = await launchBrowser();
  let exitCode = 0;
  const counters = { clicks: 0, findings: 0 };

  try {
    let ctx = await newAppContext(browser, { storageState: storagePath });
    // CRITICAL: addInitScript BEFORE the first page navigation. Pages
    // created from this context inherit the script — it runs at
    // document_start before any app JS, including before React
    // hydration of recording-client.tsx.
    await ctx.addInitScript(MEDIA_MOCK_SCRIPT);

    let page = await ctx.newPage();
    await page.goto(url, { waitUntil: 'networkidle', timeout: opts.timeout });

    // Mid-sweep session expiry: same retry shape as sweep-visit-page.
    if (page.url().includes('/login')) {
      emit({
        event: 'walker-session-refresh',
        name: 'visit-record',
        reason: 'redirect-to-login — invalidating cached storageState',
      });
      await ctx.close();
      invalidateAuthState();
      storagePath = await getOrCreateAuthState({ forceFresh: true });
      ctx = await newAppContext(browser, { storageState: storagePath });
      await ctx.addInitScript(MEDIA_MOCK_SCRIPT);
      page = await ctx.newPage();
      await page.goto(url, {
        waitUntil: 'networkidle',
        timeout: opts.timeout,
      });
    }

    // Record-page guard: status !== 'QUEUED' redirects to /visits/[id].
    // Surface that as an explicit finding rather than silently walking
    // the wrong page.
    if (page.url().includes(`/visits/${opts.visitId}`) && !page.url().endsWith('/record')) {
      emit({
        event: 'walker-result',
        name: 'visit-record',
        url,
        ok: false,
        loadErr:
          'page redirected away from /record — the recordDraft fixture is no longer status=QUEUED. Re-seed via seed-qa-fixtures.ts.',
        landedAt: page.url(),
      });
      emit({ event: 'walker-end', name: 'visit-record' });
      await ctx.close();
      exit(1);
    }

    // Confirm the media mock landed before page hydration. If the init
    // script didn't run, the rest of the walk would be untrustworthy.
    const mockBreadcrumb = await page
      .evaluate(() => window.__qaMediaMockInjected ?? null)
      .catch(() => null);
    if (!mockBreadcrumb) {
      emit({
        event: 'walker-result',
        name: 'visit-record',
        url,
        ok: false,
        loadErr:
          'media-mocks init script did not run — window.__qaMediaMockInjected missing. ' +
          'Real getUserMedia would prompt the OS in headless mode.',
      });
      emit({ event: 'walker-end', name: 'visit-record' });
      await ctx.close();
      exit(1);
    }
    emit({
      event: 'media-mock-injected',
      name: 'visit-record',
      breadcrumb: mockBreadcrumb,
    });

    // Collect a snapshot of visible affordances post-load. Mirrors the
    // enumerate() pattern in sweep-visit-page but tighter (record page
    // has very few affordances — start button, status indicator,
    // waveform area, transcript area, brand/avatar in the AppFrame).
    const elements = await page.evaluate(() => {
      const interactive = Array.from(
        document.querySelectorAll(
          'button, [role="button"], a[href^="/"], input[type="submit"]'
        )
      );
      return interactive
        .map((el) => {
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) return null;
          return {
            tag: el.tagName.toLowerCase(),
            text: (el.textContent ?? '').trim().slice(0, 80),
            disabled:
              ('disabled' in el && typeof el.disabled === 'boolean' && el.disabled) ||
              el.getAttribute('aria-disabled') === 'true',
            href: el.getAttribute('href') ?? null,
            ariaLabel: el.getAttribute('aria-label') ?? null,
            role: el.getAttribute('role'),
          };
        })
        .filter(Boolean);
    });

    for (const el of elements) {
      emit({ event: 'element', ...el });
    }

    if (!opts.skipClicks) {
      // DB-snapshot spec — clicking "Start recording" should NOT mutate
      // the visit row, so the diff stays empty after the click.
      const dbSnapshotSpec = [
        {
          table: 'transcribe_visits',
          where: `id = '${opts.visitId.replace(/'/g, "''")}'`,
        },
      ];

      // The single click we DO make: the primary "Start recording"
      // button. Locate by visible text (the button doesn't carry a
      // testid in the current shape — text-locate is the same pattern
      // sweep-visit-page uses).
      const startResult = await clickAndClassify(page, {
        name: 'start-recording',
        selector: { role: 'button', name: /start recording/i },
        dbSnapshotSpec,
        auditTargetId: opts.visitId,
        settleMs: 600,
        // Recording-state transition is purely UI — no API call expected.
        networkTimeoutMs: 1500,
      });
      counters.clicks += 1;
      emit({ event: 'click', label: 'Start recording', ...startResult });

      // Post-Start expectation: NO_NETWORK_FIRED + DOM mutated +
      // dbChanged=false + auditDelta=0. Anything else is a finding.
      const expectedClassifications = new Set([
        'NO_NETWORK_FIRED',
        'VISUAL_ONLY',
        'OK_NO_NETWORK', // Edge case — page may emit a single audit row
                          // for "VISIT_RECORDING_STARTED" in a future PR;
                          // accepting this leaves room for that addition.
      ]);
      if (!expectedClassifications.has(startResult.classification)) {
        counters.findings += 1;
        emit({
          event: 'finding',
          walker: 'visit-record',
          finding:
            `start-recording click classified as ${startResult.classification} — ` +
            `expected NO_NETWORK_FIRED / VISUAL_ONLY (recording-start is pure UI).`,
          detail: startResult,
        });
      }
      // Page should now be in 'recording' phase. Confirm via DOM —
      // status indicator should show 'RECORDING' or the dot should be
      // animating. Loose check (text presence) since the exact label
      // could change cosmetically.
      const inRecordingPhase = await page.evaluate(() => {
        const text = (document.body.innerText ?? '').toUpperCase();
        return text.includes('RECORDING');
      });
      emit({
        event: 'phase-check',
        walker: 'visit-record',
        inRecordingPhase,
      });
      if (!inRecordingPhase) {
        counters.findings += 1;
        emit({
          event: 'finding',
          walker: 'visit-record',
          finding:
            'page did not transition into RECORDING phase after Start click — ' +
            'mock may have failed silently, or page state-machine changed shape.',
        });
      }

      // The "Stop & process" button is now visible. Enumerate it so the
      // record makes the affordance visible in the report, but DO NOT
      // click it — clicking triggers a real /dictation/upload POST.
      const stopVisible = await page
        .getByRole('button', { name: /stop.*process/i })
        .first()
        .isVisible()
        .catch(() => false);
      emit({
        event: 'click-skipped',
        label: 'Stop & process',
        reason:
          'walker is read-only — Stop triggers /api/visits/<id>/dictation/upload',
        visible: stopVisible,
      });

      // Page-frame nav links (e.g. brand link, avatar) — outbound
      // affordances. Enumerate-but-don't-click per the established
      // pattern in sweep-visit-page.
      for (const el of elements) {
        if (el.tag === 'a' && el.href && !el.href.startsWith(url)) {
          emit({
            event: 'click-skipped',
            label: el.text || el.ariaLabel,
            reason: 'leaves-page',
            href: el.href,
          });
        }
      }
    }

    emit({
      event: 'walker-result',
      name: 'visit-record',
      url,
      ok: true,
      visitId: opts.visitId,
      clicks: counters.clicks,
      findings: counters.findings,
    });
    emit({ event: 'walker-end', name: 'visit-record' });
    await ctx.close();
  } catch (err) {
    emit({
      event: 'walker-result',
      name: 'visit-record',
      url,
      ok: false,
      loadErr: err.message,
      stack: err.stack,
    });
    emit({ event: 'walker-end', name: 'visit-record' });
    exitCode = 1;
  } finally {
    await browser.close();
  }
  exit(exitCode);
}

main();
