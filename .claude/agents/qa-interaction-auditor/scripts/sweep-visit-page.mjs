#!/usr/bin/env node
// ============================================================================
// sweep-visit-page.mjs
// ----------------------------------------------------------------------------
// Walks a target page in headless Chromium as the QA test user, clicks
// every visible interactive element, and emits one classification per
// click on stdout (NDJSON — one JSON object per line).
//
// The QA Interaction Auditor agent invokes this and pipes the output
// into the bug-report template in skills/reporting-format.md.
//
// Usage:
//   node sweep-visit-page.mjs --url /visits/<id>
//   node sweep-visit-page.mjs --url /visits --skip-clicks   (enumerate only)
//   node sweep-visit-page.mjs --url / --base https://app.quillmd.com
//
// Required env:
//   QA_AUDITOR_PASSWORD   bcrypt-hashed account in DB; see fixtures/test-user.md
// Optional env:
//   QA_AUDITOR_EMAIL      defaults to qa-auditor@quillmd.test
//   QA_AUDITOR_BASE_URL   defaults to https://app.quillmd.com
//
// Output (NDJSON to stdout):
//   {"event":"sweep-start", "url":"...", "ts":"..."}
//   {"event":"element", "label":"...", "tag":"button", "selector":"...", ...}
//   {"event":"click", "label":"...", "classification":"OK|NO_NETWORK_FIRED|PRETEND_SUCCESS_FALLBACK|HTTP_4xx|HTTP_5xx", ...}
//   {"event":"sweep-end", "elements":N, "clicks":N, "findings":N}
//
// Side effects:
//   - Logs in as the test user, navigates, clicks. Creates browser
//     state at run time; does NOT write to disk.
//   - Reads from postgres + caddy logs via docker exec / docker logs
//     (read-only).
//   - Aborts cleanly on Ctrl-C.
// ============================================================================

import { chromium } from '/opt/meddoc-pro/node_modules/playwright/index.mjs';
import { execSync } from 'node:child_process';
import { argv, env, exit, stderr, stdout } from 'node:process';
import { recentMutations } from './check-network-mutations.mjs';

// ---------------------------------------------------------------------------
// Args + env
// ---------------------------------------------------------------------------

function parseArgs(args) {
  const opts = {
    url: null,
    base: env.QA_AUDITOR_BASE_URL ?? 'https://app.quillmd.com',
    skipClicks: false,
    visitId: null,
    timeout: 15_000,
  };
  for (let i = 2; i < args.length; i += 1) {
    const a = args[i];
    if (a === '--url') {
      opts.url = args[i + 1];
      i += 1;
    } else if (a === '--base') {
      opts.base = args[i + 1];
      i += 1;
    } else if (a === '--visit-id') {
      opts.visitId = args[i + 1];
      i += 1;
    } else if (a === '--skip-clicks') {
      opts.skipClicks = true;
    } else if (a === '--timeout') {
      opts.timeout = Number(args[i + 1]);
      i += 1;
    } else if (a === '--help' || a === '-h') {
      stderr.write(
        'sweep-visit-page.mjs --url <path> [--base <https://...>] [--skip-clicks] [--visit-id <uuid>]\n'
      );
      exit(2);
    } else {
      stderr.write(`Unknown arg: ${a}\n`);
      exit(2);
    }
  }
  if (!opts.url) {
    stderr.write('--url is required\n');
    exit(2);
  }
  return opts;
}

const opts = parseArgs(argv);

const TEST_EMAIL = env.QA_AUDITOR_EMAIL ?? 'qa-auditor@quillmd.test';
const TEST_PASSWORD = env.QA_AUDITOR_PASSWORD;
if (!TEST_PASSWORD) {
  stderr.write('QA_AUDITOR_PASSWORD not set — see fixtures/test-user.md\n');
  exit(2);
}

function emit(obj) {
  stdout.write(`${JSON.stringify({ ts: new Date().toISOString(), ...obj })}\n`);
}

// ---------------------------------------------------------------------------
// DB snapshot helper (uses the sibling diff-db-state.sh)
// ---------------------------------------------------------------------------

function snapshotVisit(visitId, label) {
  if (!visitId) return null;
  try {
    const out = execSync(
      `${import.meta.dirname}/diff-db-state.sh snapshot ${visitId} ${label}`,
      { encoding: 'utf-8' }
    );
    return out.trim();
  } catch (err) {
    stderr.write(`snapshotVisit failed: ${err.message}\n`);
    return null;
  }
}

function diffVisit(visitId, labelA, labelB) {
  if (!visitId) return null;
  try {
    const out = execSync(
      `${import.meta.dirname}/diff-db-state.sh diff ${visitId} ${labelA} ${labelB} 2>&1`,
      { encoding: 'utf-8' }
    );
    return JSON.parse(out);
  } catch (err) {
    // Exit code 1 = changes found (still a successful diff). Non-1 = real error.
    if (err.status === 1 && err.stdout) {
      try {
        return JSON.parse(err.stdout.toString());
      } catch {
        return null;
      }
    }
    stderr.write(`diffVisit failed: ${err.message}\n`);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Click classification
// ---------------------------------------------------------------------------

function classifyClick({ response, dbDiff, mutationsAfter }) {
  if (!response && (!mutationsAfter || mutationsAfter.length === 0)) {
    return 'NO_NETWORK_FIRED';
  }
  const status = response?.status() ?? mutationsAfter?.[0]?.status ?? null;
  if (status === null) return 'UNKNOWN';
  if (status >= 200 && status < 300) {
    if (!dbDiff || dbDiff.changed === false) {
      return 'PRETEND_SUCCESS_FALLBACK';
    }
    return 'OK';
  }
  if (status >= 400 && status < 500) return `HTTP_${status}`;
  if (status >= 500) return `HTTP_${status}`;
  return `HTTP_${status}`;
}

// ---------------------------------------------------------------------------
// Sweep
// ---------------------------------------------------------------------------

async function login(page) {
  await page.goto('/login', { waitUntil: 'domcontentloaded' });
  await page.fill('input[type="email"]', TEST_EMAIL);
  await page.fill('input[type="password"]', TEST_PASSWORD);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: opts.timeout }),
    page.click('button[type="submit"]'),
  ]);
}

async function enumerate(page) {
  return page.$$eval(
    'button, [role="button"], a[href^="/"], input[type="submit"]',
    (els) =>
      els
        .map((el, i) => {
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) return null;
          const tag = el.tagName.toLowerCase();
          return {
            index: i,
            tag,
            text: (el.textContent ?? '').trim().slice(0, 80),
            disabled:
              'disabled' in el && typeof el.disabled === 'boolean'
                ? el.disabled
                : el.getAttribute('aria-disabled') === 'true',
            href: el.getAttribute('href') ?? null,
            ariaLabel: el.getAttribute('aria-label') ?? null,
            role: el.getAttribute('role'),
            // Cheap, stable selector — the agent re-locates by index
            // because the DOM may mutate between enumerate and click.
            uniqueText:
              (el.getAttribute('aria-label') ?? '') +
              '|' +
              (el.textContent ?? '').trim().slice(0, 40),
          };
        })
        .filter(Boolean)
  );
}

async function clickAndClassify(page, element, opts) {
  const beforeMutations = recentMutations({ since: '5s' });
  if (opts.visitId) snapshotVisit(opts.visitId, 'before');

  // Re-locate by aria-label or visible text.
  const locator = element.ariaLabel
    ? page.getByRole(element.role ?? 'button', { name: element.ariaLabel })
    : page.getByText(element.text || element.uniqueText, { exact: false }).first();

  let response = null;
  try {
    [response] = await Promise.all([
      page
        .waitForResponse(
          (r) => {
            const m = r.request().method();
            const u = r.url();
            return m !== 'GET' && (u.includes('/api/') || u.includes('/visits/'));
          },
          { timeout: 5_000 }
        )
        .catch(() => null),
      locator.click({ timeout: 3_000 }),
    ]);
  } catch (err) {
    return {
      classification: 'CLICK_THREW',
      error: err.message,
      networkRequest: null,
      dbDiff: null,
    };
  }

  // Settle: small DOM-mutation grace window.
  await page.waitForTimeout(800);

  const afterMutations = recentMutations({ since: '8s' });
  const newMutations = afterMutations.slice(beforeMutations.length);

  let dbDiff = null;
  if (opts.visitId) {
    snapshotVisit(opts.visitId, 'after');
    dbDiff = diffVisit(opts.visitId, 'before', 'after');
  }

  return {
    classification: classifyClick({ response, dbDiff, mutationsAfter: newMutations }),
    networkRequest: response
      ? { url: response.url(), method: response.request().method(), status: response.status() }
      : null,
    networkSnapshot: newMutations,
    dbDiff,
  };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    baseURL: opts.base,
    colorScheme: 'dark',
    reducedMotion: 'reduce',
    storageState: undefined,
  });

  let counters = { elements: 0, clicks: 0, findings: 0 };
  let exitCode = 0;

  try {
    const page = await ctx.newPage();

    emit({ event: 'sweep-start', url: opts.url, base: opts.base });

    await login(page);
    await page.goto(opts.url, { waitUntil: 'networkidle', timeout: opts.timeout });

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
        // Skip outbound nav links — clicking them leaves the page and
        // we'd need full state restoration. Enumerate them but don't click.
        if (el.tag === 'a' && el.href && !el.href.startsWith(opts.url)) {
          emit({ event: 'click-skipped', label: el.text, reason: 'leaves-page', href: el.href });
          continue;
        }

        const result = await clickAndClassify(page, el, opts);
        counters.clicks += 1;

        if (
          result.classification === 'NO_NETWORK_FIRED' ||
          result.classification === 'PRETEND_SUCCESS_FALLBACK' ||
          result.classification === 'CLICK_THREW' ||
          result.classification.startsWith('HTTP_5')
        ) {
          counters.findings += 1;
        }

        emit({ event: 'click', label: el.text, ...result });

        // Re-navigate to the target URL after each click so the next
        // element comes from a stable state. Click sequences that need
        // ordering should be expressed as a workflow walk, not a sweep.
        await page.goto(opts.url, { waitUntil: 'networkidle', timeout: opts.timeout });
      }
    }

    emit({ event: 'sweep-end', ...counters });
  } catch (err) {
    emit({ event: 'sweep-error', message: err.message, stack: err.stack });
    exitCode = 1;
  } finally {
    await ctx.close();
    await browser.close();
  }

  exit(exitCode);
}

main();
