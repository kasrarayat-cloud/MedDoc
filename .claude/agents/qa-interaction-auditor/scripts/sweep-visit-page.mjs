#!/usr/bin/env node
// ============================================================================
// sweep-visit-page.mjs — flagship deep walker (✅ tier)
// ----------------------------------------------------------------------------
// Walks every interactive element on the visit-ready page as the QA
// test user. Per element:
//   - Snapshots transcribe_visits row + audit_logs count BEFORE click
//   - Clicks the element + waits for network-idle
//   - Snapshots same tables AFTER, classifies the outcome
//   - Re-navigates to the target URL between clicks for stable state
//
// v3.1 refactor (proof-of-shape for the deepWalk helper):
//   - Auth via lib/walker-base.mjs getOrCreateAuthState (session
//     reuse — no per-walker login)
//   - Click classification + table snapshotting via walker-base
//     primitives (snapshotTables, clickAndClassify)
//   - --scenario flag resolves to one of the 4 fixture visit ids
//     so the walker can exercise different code paths
//
// Usage:
//   node sweep-visit-page.mjs --url /visits/<id>
//   node sweep-visit-page.mjs --scenario bumpEligible
//   node sweep-visit-page.mjs --visit-id <id> --skip-clicks
//
// Output: NDJSON to stdout — one record per element / click / event.
// ============================================================================

import { existsSync, readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { argv, env, exit, stderr, stdout } from 'node:process';

import {
  emit,
  getOrCreateAuthState,
  invalidateAuthState,
  launchBrowser,
  newAppContext,
  clickAndClassify,
  snapshotTables,
  snapshotAuditCount,
} from './lib/walker-base.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SEEDED_IDS_PATH = resolve(__dirname, '..', 'fixtures', 'seeded-ids.json');

function resolveScenarioToVisitId(scenario) {
  if (!scenario) return null;
  if (!existsSync(SEEDED_IDS_PATH)) return null;
  try {
    const seeded = JSON.parse(readFileSync(SEEDED_IDS_PATH, 'utf-8'));
    return seeded.visitIds?.[scenario] ?? null;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Args
// ---------------------------------------------------------------------------

function parseArgs(args) {
  const opts = {
    url: null,
    base: env.QA_AUDITOR_BASE_URL ?? 'https://app.quillmd.com',
    skipClicks: false,
    visitId: null,
    scenario: env.QA_SCENARIO ?? null,
    timeout: 15_000,
  };
  for (let i = 2; i < args.length; i += 1) {
    const a = args[i];
    if (a === '--url') { opts.url = args[i + 1]; i += 1; }
    else if (a === '--base') { opts.base = args[i + 1]; i += 1; }
    else if (a === '--visit-id') { opts.visitId = args[i + 1]; i += 1; }
    else if (a === '--scenario') { opts.scenario = args[i + 1]; i += 1; }
    else if (a === '--skip-clicks') { opts.skipClicks = true; }
    else if (a === '--timeout') { opts.timeout = Number(args[i + 1]); i += 1; }
    else if (a === '--help' || a === '-h') {
      stderr.write(
        'sweep-visit-page.mjs --url <path> | --scenario <key> | --visit-id <id>\n' +
          '  --scenario one of: bumpEligible | criticalRx | pediatric | nonClinical\n'
      );
      exit(2);
    } else {
      stderr.write(`Unknown arg: ${a}\n`);
      exit(2);
    }
  }

  if (opts.scenario && !opts.visitId) {
    const vid = resolveScenarioToVisitId(opts.scenario);
    if (!vid) {
      stderr.write(
        `Scenario '${opts.scenario}' not found in seeded-ids.json. ` +
          'Run apps/transcribe-md/scripts/seed-qa-fixtures.ts first.\n'
      );
      exit(2);
    }
    opts.visitId = vid;
    if (!opts.url) opts.url = `/visits/${vid}`;
  }
  if (!opts.visitId && env.QA_FIXTURE_VISIT_ID) {
    opts.visitId = env.QA_FIXTURE_VISIT_ID;
    if (!opts.url) opts.url = `/visits/${opts.visitId}`;
  }
  if (!opts.url) {
    stderr.write(
      '--url required (or pass --scenario / QA_SCENARIO / QA_FIXTURE_VISIT_ID)\n'
    );
    exit(2);
  }
  return opts;
}

const opts = parseArgs(argv);

// ---------------------------------------------------------------------------
// DOM enumeration — same shape as the v2 walker, but the click loop
// below routes each element through walker-base's clickAndClassify
// instead of bespoke logic.
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

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  emit({ event: 'sweep-start', url: opts.url, base: opts.base, visitId: opts.visitId });

  let storagePath;
  try {
    storagePath = await getOrCreateAuthState();
  } catch (err) {
    emit({ event: 'sweep-error', stage: 'login', message: err.message });
    exit(1);
  }

  const browser = await launchBrowser();
  let exitCode = 0;
  const counters = { elements: 0, clicks: 0, findings: 0 };

  try {
    let ctx = await newAppContext(browser, { storageState: storagePath });
    let page = await ctx.newPage();

    await page.goto(opts.url, {
      waitUntil: 'networkidle',
      timeout: opts.timeout,
    });

    // If the cached session expired and the page bounced to /login,
    // refresh storageState once and retry the navigation.
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
      await page.goto(opts.url, {
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
      // The DB-snapshot spec for the visit-ready page: rows the
      // visit-ready interactions can mutate.
      const dbSnapshotSpec = opts.visitId
        ? [
            {
              table: 'transcribe_visits',
              where: `id = '${opts.visitId.replace(/'/g, "''")}'`,
            },
          ]
        : [];

      for (const el of elements) {
        if (el.disabled) {
          emit({ event: 'click-skipped', label: el.text, reason: 'disabled' });
          continue;
        }
        // Outbound nav links would leave the page; enumerate but don't click.
        if (el.tag === 'a' && el.href && !el.href.startsWith(opts.url)) {
          emit({
            event: 'click-skipped',
            label: el.text,
            reason: 'leaves-page',
            href: el.href,
          });
          continue;
        }

        // Build a Playwright-flavored selector spec for clickAndClassify.
        const selectorSpec = el.ariaLabel
          ? { role: el.role ?? 'button', name: el.ariaLabel }
          : { text: el.text || el.ariaLabel || '?', exact: false };

        const result = await clickAndClassify(page, {
          name: el.text || el.ariaLabel || `(${el.tag})`,
          selector: selectorSpec,
          dbSnapshotSpec,
          auditTargetId: opts.visitId,
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
        await page.goto(opts.url, {
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
      name: 'visit-page',
      url: opts.url,
      ok: true,
      durationMs: 0,
      ...counters,
    });
    await ctx.close();
  } catch (err) {
    emit({ event: 'sweep-error', message: err.message, stack: err.stack });
    emit({
      event: 'walker-result',
      name: 'visit-page',
      url: opts.url,
      ok: false,
      loadErr: err.message,
    });
    exitCode = 1;
  } finally {
    await browser.close();
  }
  exit(exitCode);
}

main();
