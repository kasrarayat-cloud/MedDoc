#!/usr/bin/env node
// ============================================================================
// sweep-board.mjs — /board deep walker (✅ transactional tier)
// ----------------------------------------------------------------------------
// Rounds Screen 1. Added for item F (the flip), 2026-08-02, because the
// walker fleet had ZERO Rounds coverage: `/board` appeared in no site-map
// row, no WALKERS registry entry, and no walker's element map — while the
// route has existed and shipped dark since Phase A.
//
// ⚠️ THIS WALKER REQUIRES A FLAG-ON IMAGE. `NEXT_PUBLIC_SKIN_ROUNDS` is a
// build-time inlined constant, and `board/page.tsx` runs
// `if (!isSkinRounds()) notFound()` BEFORE auth(). Against a flag-OFF build
// the route 404s, so a walk would "pass" by walking a 404 — an answer about
// a page that is not the page. main() asserts the board actually rendered
// (data-testid="rounds-board" | "rounds-board-empty") and fails loudly if
// not, rather than reporting ok:true over an empty set.
//
// WHAT MAY BE CLICKED, AND WHY
//
//   Filter pills (rounds-filter-*)  — <Link> with a query param. Same route,
//   Pagination    (rounds-page-*)     server-rendered, no write.
//   Search submit                    — GET form (name="q"), same route.
//
//   These are the board's natural zero-write assertions, the same shape as
//   the existing /visits filter-pill check.
//
// WHAT MUST NOT BE CLICKED
//
//   "Retry"  — RoundsRetryButton (retry-button.tsx:36) POSTs
//              /api/visits/[id]/retry, which RE-QUEUES process-visit: a real
//              BullMQ job, a real model call on the shared Anthropic balance,
//              and a status write on somebody's visit. It renders in the
//              board grid with the plain label "Retry" and matched no
//              existing FORBIDDEN_BUTTONS pattern — the deny-list was silent
//              on the one write this screen surfaces. Denied here and in
//              sweep-visit-page.mjs.
//
//   Lane cards / "Open next review →" — navigate to /visits/[id]. Reads, not
//              writes, but they leave the page and log a VIEWED_VISIT row
//              against a visit this walk is not about. Enumerated, not
//              clicked, per the existing `leaves-page` convention.
//
// THE AUDIT ROW THAT IS SUPPOSED TO BE THERE
//
//   The board's RSC writes `VIEWED_VISIT_LIST` on EVERY render
//   (board/page.tsx:124). So "zero writes" on this screen does NOT mean zero
//   audit rows — it means zero rows of any OTHER action, and zero change to
//   transcribe_visits. A walker asserting delta == 0 here would fail on
//   correct behaviour; one ignoring audit rows entirely would miss a real
//   write. This walker counts by action and names the expected one.
//
// CLI:
//   node sweep-board.mjs                  # walk /board
//   node sweep-board.mjs --skip-clicks    # enumerate only
//   node sweep-board.mjs --url /board?filter=needs-review
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
  snapshotCounts,
  ingressLogSource,
  APP_BASE,
} from './lib/walker-base.mjs';

// ---------------------------------------------------------------------------
// Deny-list — labels this walker refuses to click.
// ---------------------------------------------------------------------------
const FORBIDDEN_BUTTONS = [
  {
    pattern: /\bretry(ing)?\b/i,
    risk: 'would-requeue-the-ai-pipeline',
    note:
      'RoundsRetryButton POSTs /api/visits/[id]/retry → re-queues process-visit. ' +
      'A real job, a real model call, a real status write.',
  },
  {
    pattern: /\bsign\b/i,
    risk: 'would-sign-a-clinical-note',
    note: 'nothing on the board should sign, but the deny-list fails closed.',
  },
];

function forbiddenMatch(label) {
  const text = (label ?? '').trim();
  if (!text) return null;
  for (const entry of FORBIDDEN_BUTTONS) {
    if (entry.pattern.test(text)) return entry;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Args
// ---------------------------------------------------------------------------
function parseArgs(args) {
  const opts = {
    url: '/board',
    base: env.QA_AUDITOR_BASE_URL ?? APP_BASE,
    skipClicks: false,
    timeout: 20_000,
  };
  for (let i = 2; i < args.length; i += 1) {
    const a = args[i];
    if (a === '--url') { opts.url = args[i + 1]; i += 1; }
    else if (a === '--base') { opts.base = args[i + 1]; i += 1; }
    else if (a === '--skip-clicks') { opts.skipClicks = true; }
    else if (a === '--timeout') { opts.timeout = Number(args[i + 1]); i += 1; }
    else if (a === '--help' || a === '-h') {
      stderr.write('sweep-board.mjs [--url /board] [--skip-clicks] [--timeout ms]\n');
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
// DOM enumeration — built at RUNTIME, like every other walker. The board has
// 129 distinct qm-rounds-* classes; a hand-written selector list would be
// stale the first time the grid changes.
// ---------------------------------------------------------------------------
async function enumerate(page) {
  return page.$$eval(
    'button, [role="button"], a[href], input, [role="combobox"]',
    (els) =>
      els
        .map((el, i) => {
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) return null;
          return {
            index: i,
            tag: el.tagName.toLowerCase(),
            type: el.getAttribute('type'),
            text: (el.textContent ?? '').trim().slice(0, 80),
            disabled:
              'disabled' in el && typeof el.disabled === 'boolean'
                ? el.disabled
                : el.getAttribute('aria-disabled') === 'true',
            href: el.getAttribute('href') ?? null,
            ariaLabel: el.getAttribute('aria-label') ?? null,
            role: el.getAttribute('role'),
            testId: el.getAttribute('data-testid'),
          };
        })
        .filter(Boolean)
  );
}

/** Safe-to-click decision for /board. */
function classifyForClickSafety(el) {
  if (el.disabled) return { safe: false, reason: 'disabled' };

  const forbidden = forbiddenMatch(el.text || el.ariaLabel);
  if (forbidden) {
    return {
      safe: false,
      reason: 'forbidden-write',
      risk: forbidden.risk,
      note: forbidden.note,
    };
  }

  // Anything navigating off /board: lane cards, "Open next review →", the
  // chrome's outbound links. Enumerate, don't click.
  if (el.tag === 'a' && el.href) {
    const path = el.href.split('?')[0];
    if (path !== '' && path !== '/board') {
      return { safe: false, reason: 'leaves-page', href: el.href };
    }
  }

  return { safe: true };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
async function main() {
  emit({
    event: 'sweep-start',
    walker: 'board',
    url: opts.url,
    base: opts.base,
    ingressLog: ingressLogSource(),
  });

  let storagePath;
  try {
    storagePath = await getOrCreateAuthState();
  } catch (err) {
    emit({ event: 'sweep-error', stage: 'login', message: err.message });
    emit({ event: 'walker-result', name: 'board', url: opts.url, ok: false, loadErr: err.message });
    exit(1);
  }

  const browser = await launchBrowser();
  let exitCode = 0;
  const counters = { elements: 0, clicks: 0, skipped: 0, findings: 0 };

  try {
    let ctx = await newAppContext(browser, { storageState: storagePath });
    let page = await ctx.newPage();

    await page.goto(opts.url, { waitUntil: 'networkidle', timeout: opts.timeout });

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
      await page.goto(opts.url, { waitUntil: 'networkidle', timeout: opts.timeout });
    }

    // ── The premise check. A flag-OFF build 404s this route, and a walk of a
    //    404 would enumerate nothing, click nothing, and report ok:true. Prove
    //    the board is actually on screen before believing any later zero.
    const boardPresent =
      (await page.getByTestId('rounds-board').count()) > 0 ||
      (await page.getByTestId('rounds-board-empty').count()) > 0;
    const skinAttr = await page.evaluate(
      () => document.documentElement.getAttribute('data-skin')
    );
    emit({ event: 'premise', boardPresent, dataSkin: skinAttr, url: page.url() });

    if (!boardPresent || skinAttr !== 'rounds') {
      emit({
        event: 'sweep-error',
        stage: 'premise',
        message:
          `the board did not render (boardPresent=${boardPresent}, ` +
          `data-skin=${JSON.stringify(skinAttr)}). This is a flag-OFF build or ` +
          `a 404 — refusing to report a walk of a page that is not the board.`,
      });
      emit({
        event: 'walker-result',
        name: 'board',
        url: opts.url,
        ok: false,
        loadErr: 'premise-failed: board not rendered / data-skin not "rounds"',
        ...counters,
      });
      await ctx.close();
      await browser.close();
      exit(1);
    }

    const elements = await enumerate(page);
    counters.elements = elements.length;
    for (const el of elements) emit({ event: 'element', ...el });

    if (!opts.skipClicks) {
      // Zero-write spec. COUNTS, not rows: the question is "did anything get
      // written", and a count never pulls soapDraft/soapFinal into memory.
      //
      // `otherAudit` deliberately EXCLUDES VIEWED_VISIT_LIST — the board's RSC
      // writes one on every render, so it is expected behaviour, not a finding.
      // Any other action appearing during a board click is the finding.
      const countSpec = [
        { label: 'visits', table: 'transcribe_visits', where: 'TRUE' },
        {
          label: 'visitsWrittenRecently',
          table: 'transcribe_visits',
          where: `"updatedAt" > NOW() - INTERVAL '2 minutes'`,
        },
        {
          label: 'otherAudit',
          table: 'audit_logs',
          where:
            `timestamp > NOW() - INTERVAL '2 minutes' ` +
            `AND action::text <> 'VIEWED_VISIT_LIST'`,
        },
      ];

      for (const el of elements) {
        const safety = classifyForClickSafety(el);
        if (!safety.safe) {
          emit({
            event: 'click-skipped',
            label: el.text || el.ariaLabel || '?',
            tag: el.tag,
            testId: el.testId,
            ...safety,
          });
          counters.skipped += 1;
          continue;
        }

        const before = snapshotCounts(countSpec);

        // Selector precedence: testId → accessible role+name → bare text.
        //
        // The bare-text fallback is LAST for a reason found on the first real
        // walk: `{ text: 'Search' }` resolved to `<label class="sr-only">Search
        // visits</label>` rather than the `<button>Search</button>` beside it,
        // and the form then intercepted the pointer — a 4s CLICK_THREW against
        // an element the walker was never aiming at. A role-scoped lookup
        // cannot make that mistake, and every enumerated node already carries
        // the tag needed to name its role.
        const roleFor = el.role ?? (el.tag === 'a' ? 'link' : el.tag === 'button' ? 'button' : null);
        const accessibleName = el.ariaLabel || el.text;
        const selectorSpec = el.testId
          ? { testId: el.testId }
          : roleFor && accessibleName
            ? { role: roleFor, name: accessibleName }
            : { text: el.text || `(${el.tag})`, exact: false };

        let result = await clickAndClassify(page, {
          name: el.text || el.ariaLabel || el.testId || `(${el.tag})`,
          selector: selectorSpec,
          // The board has no single visit to attribute audits to; the
          // action-scoped counts below carry the assertion instead.
          auditTargetId: null,
          settleMs: 700,
        });

        // A role+name miss is "I could not look", not "nothing happened" — and
        // an unexercised control reported as a clean walk is the whole failure
        // class this harness exists to avoid. Fall back to text ONCE so the
        // element is actually exercised. (Real case: the brand link enumerates
        // as "QQuillMD" — logo glyph plus wordmark — so its accessible name
        // never equals its textContent.)
        if (result.classification === 'HIDDEN_OR_MISSING' && !selectorSpec.testId && selectorSpec.role) {
          emit({
            event: 'selector-fallback',
            label: el.text || el.testId,
            from: selectorSpec,
            to: { text: el.text, exact: false },
          });
          result = await clickAndClassify(page, {
            name: el.text || `(${el.tag})`,
            selector: { text: el.text || `(${el.tag})`, exact: false },
            auditTargetId: null,
            settleMs: 700,
          });
        }
        counters.clicks += 1;

        const after = snapshotCounts(countSpec);

        // A null on either side is a FAILED probe, not a zero. Say so, and let
        // walker-base's emit() downgrade ok for the recorded dbError.
        const unmeasured = Object.keys(before).filter(
          (k) => before[k] === null || after[k] === null
        );

        const deltas = {};
        for (const k of Object.keys(before)) {
          deltas[k] =
            before[k] === null || after[k] === null ? null : after[k] - before[k];
        }

        if (deltas.visits !== 0 || deltas.visitsWrittenRecently > 0) {
          counters.findings += 1;
          emit({
            event: 'finding',
            kind: 'unexpected-db-write',
            label: el.text || el.testId,
            table: 'transcribe_visits',
            deltas,
            classification: result.classification,
          });
        }
        if (deltas.otherAudit > 0) {
          counters.findings += 1;
          emit({
            event: 'finding',
            kind: 'unexpected-audit-row',
            label: el.text || el.testId,
            note:
              'a board click wrote an audit row that is not VIEWED_VISIT_LIST',
            deltas,
            classification: result.classification,
          });
        }
        if (
          result.classification === 'CLICK_THREW' ||
          (typeof result.classification === 'string' &&
            result.classification.startsWith('HTTP_5'))
        ) {
          counters.findings += 1;
        }

        emit({
          event: 'click',
          label: el.text || el.testId,
          testId: el.testId,
          deltas,
          unmeasured: unmeasured.length ? unmeasured : undefined,
          ...result,
        });

        // Filters and pagination change the URL; return to the walk's starting
        // state so the next locator resolves against the same board.
        await page.goto(opts.url, { waitUntil: 'networkidle', timeout: opts.timeout });
      }
    }

    emit({ event: 'sweep-end', ...counters });
    emit({
      event: 'walker-result',
      name: 'board',
      url: opts.url,
      ok: true,
      durationMs: 0,
      ingressLog: ingressLogSource(),
      ...counters,
    });
    await ctx.close();
  } catch (err) {
    emit({ event: 'sweep-error', message: err.message, stack: err.stack });
    emit({
      event: 'walker-result',
      name: 'board',
      url: opts.url,
      ok: false,
      loadErr: err.message,
      ...counters,
    });
    exitCode = 1;
  } finally {
    await browser.close();
  }
  exit(exitCode);
}

main();
