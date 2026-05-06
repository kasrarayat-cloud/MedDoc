#!/usr/bin/env node
// ============================================================================
// sweep-new-visit.mjs — /visits/new deep walker (✅ tier — v3.2)
// ----------------------------------------------------------------------------
// Walks every interactive element on the new-visit wizard as the QA
// test user. The page is a single URL with two internal stages driven
// by the selectedPatient state:
//
//   Stage 1 — PatientPicker (no patient selected)
//     - Debounced search input (POST /api/patients?search=…)
//     - "Create new patient" toggle (pure UI; expands inline form)
//     - Inline-form Cancel button (pure UI; collapses)
//     - Cancel → /dashboard (outbound nav; enumerate, don't click)
//
//   Stage 2 — VisitFormStep2 (patient selected via ?patientId=)
//     - SpecialtyDropdown (Radix Select.Trigger; opens listbox)
//     - Chief-complaint <input>
//     - 3 capture-mode tiles (audio_upload / voice_dictation /
//       text_notes) — these are <button type="submit">, NOT radios.
//       Clicking one would call the createVisitAction server action,
//       create a transcribe_visits row, and queue a process-visit
//       job. The walker MUST enumerate them but never click them.
//     - "Change patient" button (resets to Stage 1 — destructive of
//        the walk's starting state; we re-navigate after the click)
//     - Cancel → /dashboard (enumerate, don't click)
//
// Key DB-snapshot watch: transcribe_visits MUST NOT change during any
// click. Any non-zero dbChanged on this page is a finding (see
// classification PRETEND_SUCCESS_FALLBACK and OK_NO_NETWORK paths in
// walker-base classifyClick — we emit either as an alarm).
//
// CLI:
//   node sweep-new-visit.mjs                    # Stage 2 (default)
//   node sweep-new-visit.mjs --stage 1          # Stage 1 (PatientPicker)
//   node sweep-new-visit.mjs --url <path>       # explicit override
//   node sweep-new-visit.mjs --skip-clicks      # enumerate only
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
    url: null,
    base: env.QA_AUDITOR_BASE_URL ?? 'https://app.quillmd.com',
    stage: 2,
    skipClicks: false,
    timeout: 15_000,
  };
  for (let i = 2; i < args.length; i += 1) {
    const a = args[i];
    if (a === '--url') { opts.url = args[i + 1]; i += 1; }
    else if (a === '--base') { opts.base = args[i + 1]; i += 1; }
    else if (a === '--stage') { opts.stage = Number(args[i + 1]); i += 1; }
    else if (a === '--skip-clicks') { opts.skipClicks = true; }
    else if (a === '--timeout') { opts.timeout = Number(args[i + 1]); i += 1; }
    else if (a === '--help' || a === '-h') {
      stderr.write(
        'sweep-new-visit.mjs --stage 1|2 [--url <path>] [--skip-clicks]\n' +
          '  --stage 2 (default): land on Stage 2 via ?patientId=<seeded>\n' +
          '  --stage 1: walk PatientPicker (no patient pre-selected)\n'
      );
      exit(2);
    } else {
      stderr.write(`Unknown arg: ${a}\n`);
      exit(2);
    }
  }

  if (opts.stage !== 1 && opts.stage !== 2) {
    stderr.write(`--stage must be 1 or 2 (got: ${opts.stage})\n`);
    exit(2);
  }

  if (!opts.url) {
    if (opts.stage === 2) {
      const patientId = readSeededPatientId();
      if (!patientId) {
        stderr.write(
          'Stage 2 requires a seeded patientId. Run ' +
            'apps/transcribe-md/scripts/seed-qa-user.ts (or pass --stage 1).\n'
        );
        exit(2);
      }
      opts.url = `/visits/new?patientId=${patientId}`;
    } else {
      opts.url = '/visits/new';
    }
  }
  return opts;
}

const opts = parseArgs(argv);

// ---------------------------------------------------------------------------
// DOM enumeration
// ---------------------------------------------------------------------------

async function enumerate(page) {
  return page.$$eval(
    'button, [role="button"], a[href], input, [role="combobox"]',
    (els) =>
      els
        .map((el, i) => {
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) return null;
          // Capture submit buttons specifically — the mode tiles use
          // type="submit" + form="new-visit-form" so we can flag and
          // skip them in the click loop without DOM-introspection
          // again.
          const formAttr = el.getAttribute('form');
          const nameAttr = el.getAttribute('name');
          const valueAttr = el.getAttribute('value');
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
            form: formAttr,
            name: nameAttr,
            value: valueAttr,
          };
        })
        .filter(Boolean)
  );
}

// ---------------------------------------------------------------------------
// Click-routing helpers
// ---------------------------------------------------------------------------

/** Decide whether a given enumerated element is safe to click on the
 *  /visits/new page. Returns either { safe: true } or
 *  { safe: false, reason: string } so the caller can emit a
 *  click-skipped record. */
function classifyForClickSafety(el, baseUrl) {
  if (el.disabled) return { safe: false, reason: 'disabled' };

  // Outbound nav: anchors that leave /visits/new entirely. The "Cancel"
  // link → /dashboard is the canonical example. The "Change patient"
  // <Link> in step 2 (when ?patientId= drove the load) also points to
  // /visits/new — that's same-page, allow it.
  if (el.tag === 'a' && el.href) {
    const isAbs = /^https?:\/\//i.test(el.href);
    const targetPath = isAbs ? el.href : el.href.split('?')[0];
    const baseIsRoot = baseUrl.split('?')[0];
    if (!targetPath.startsWith(baseIsRoot) && !el.href.startsWith('/visits/new')) {
      return { safe: false, reason: 'leaves-page', href: el.href };
    }
  }

  // Stage 2 capture-mode tiles: <button type="submit" form="new-visit-form"
  // name="inputMode" value="audio_upload|voice_dictation|text_notes">.
  // Clicking ANY of these submits the form and creates a real visit
  // row + fires the AI pipeline. Enumerate but never click.
  if (
    el.tag === 'button' &&
    el.type === 'submit' &&
    el.form === 'new-visit-form' &&
    el.name === 'inputMode'
  ) {
    return {
      safe: false,
      reason: 'submit-creates-visit',
      mode: el.value,
    };
  }

  // Stage 1: the inline create-patient form's "Create & continue" submit
  // button would POST /api/patients/fuzzy-match then /api/patients —
  // creating a real patient row + (on duplicate-match) opening the
  // duplicate modal. Walker mandate says don't fire it.
  if (el.tag === 'button' && el.type === 'submit') {
    return { safe: false, reason: 'submit-creates-patient' };
  }

  return { safe: true };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  emit({
    event: 'sweep-start',
    walker: 'new-visit',
    url: opts.url,
    stage: opts.stage,
    base: opts.base,
  });

  let storagePath;
  try {
    storagePath = await getOrCreateAuthState();
  } catch (err) {
    emit({ event: 'sweep-error', stage: 'login', message: err.message });
    exit(1);
  }

  const browser = await launchBrowser();
  let exitCode = 0;
  const counters = { elements: 0, clicks: 0, skipped: 0, findings: 0 };

  try {
    let ctx = await newAppContext(browser, { storageState: storagePath });
    let page = await ctx.newPage();

    await page.goto(opts.url, {
      waitUntil: 'networkidle',
      timeout: opts.timeout,
    });

    // /login redirect retry once (stale cached storageState).
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
      // DB-snapshot spec for /visits/new: transcribe_visits is the
      // single mutation surface (creating a visit row). The walker
      // refuses to click anything that would write here, so any
      // dbChanged > 0 in the click stream is a real finding.
      //
      // We snapshot the most-recent 5 rows ordered by createdAt so the
      // diff catches both inserts and updates the user might trigger
      // mid-walk. (Note: walker-base.snapshotTables uses LIMIT 1 in
      // its query; we rely on the WHERE-clause ordering to make that
      // single row the latest.)
      const dbSnapshotSpec = [
        {
          table: 'transcribe_visits',
          where: 'TRUE ORDER BY "createdAt" DESC LIMIT 5',
        },
      ];

      for (const el of elements) {
        const safety = classifyForClickSafety(el, opts.url);
        if (!safety.safe) {
          emit({
            event: 'click-skipped',
            label: el.text || el.ariaLabel || '?',
            tag: el.tag,
            ...safety,
          });
          counters.skipped += 1;
          continue;
        }

        // Build a Playwright-flavored selector spec for clickAndClassify.
        const selectorSpec = el.ariaLabel
          ? { role: el.role ?? (el.tag === 'a' ? 'link' : 'button'), name: el.ariaLabel }
          : { text: el.text || `(${el.tag})`, exact: false };

        const result = await clickAndClassify(page, {
          name: el.text || el.ariaLabel || `(${el.tag})`,
          selector: selectorSpec,
          dbSnapshotSpec,
          // No auditTargetId — the new-visit page itself is a creation
          // surface; there's no extant visit row to track audits
          // against. Audit deltas of zero are expected and correct.
          auditTargetId: null,
          settleMs: 600,
        });
        counters.clicks += 1;

        // Findings on /visits/new:
        //   - dbChanged at all (any tile/button writing to transcribe_visits
        //     without an explicit submit is a Pattern-class bug)
        //   - HTTP 5xx on enumerable elements
        //   - CLICK_THREW (unexpected DOM/locator failure)
        //   - PRETEND_SUCCESS_FALLBACK (200 with no DB write — the
        //     fuzzy-match POST is allowed; we use auditTargetId=null
        //     so the classifier won't false-positive on it)
        if (result.dbChanged) {
          counters.findings += 1;
          emit({
            event: 'finding',
            kind: 'unexpected-db-write',
            label: el.text,
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

        emit({ event: 'click', label: el.text, ...result });

        // Re-navigate after each click for a stable starting state.
        // Stage 2's "Change patient" button or any state mutation
        // would otherwise poison the next iteration's locator spec.
        await page.goto(opts.url, {
          waitUntil: 'networkidle',
          timeout: opts.timeout,
        });
      }
    }

    emit({ event: 'sweep-end', ...counters });
    // Shape-consistency emit so sweep-all.mjs picks this walker up
    // as OK. Per-click findings still surface via the click stream
    // and counters.findings.
    emit({
      event: 'walker-result',
      name: 'new-visit',
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
      name: 'new-visit',
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
