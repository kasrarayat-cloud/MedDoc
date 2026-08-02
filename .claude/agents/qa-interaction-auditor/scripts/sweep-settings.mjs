#!/usr/bin/env node
// ============================================================================
// sweep-settings.mjs — /settings deep walker (✅ tier, v3.2)
// ----------------------------------------------------------------------------
// THIS IS THE MOST DELICATE WALKER IN THE FLEET.
//
// /settings exposes a 6-section sticky-anchor form (profile / security /
// sessions / data / billing / danger-zone). Many of the buttons would
// IRREVERSIBLY DAMAGE the QA test user's account or terminate the
// agent's own session if clicked. We enumerate them, log a
// `click-skipped` event with reason='destructive-not-clicked', and
// move on. The non-destructive surface (anchor links, ProfileForm
// "Save profile" with unchanged fields, the disabled "Manage billing"
// stub) is walked normally.
//
// Page layout (from src/app/settings/page.tsx):
//   - Sticky aside with 6 anchor links (#profile, #security, #sessions,
//     #data, #billing, #danger) — IN-PAGE, safe to click; verifies
//     scroll-anchor behaviour.
//   - Section 01 / Profile — ProfileForm (display name / specialty /
//     NPI / clinic name / time zone). Save button is a server-action
//     submit. Safe to click ONCE because we don't fill anything (the
//     submitted FormData equals the current row → no-op update). Email
//     row hosts a "Change" trigger → opens ChangeEmailDialog → don't
//     submit (would fire a confirmation email).
//   - Section 02 / Security — ChangePasswordForm (POST /api/settings/
//     change-password). The submit button is GATED disabled until all
//     three password fields are non-empty, so an enumeration click is
//     a no-op. We DO NOT fill the fields — submitting would reset the
//     QA password. MFA card is read-only copy.
//   - Section 03 / Sessions — SessionPanel renders the active-session
//     dl + "Sign out" + "Sign out all devices" buttons. Both DESTROY
//     the agent's own session. Enumerate, never click.
//   - Section 04 / Data — "Export my data" anchor → /api/settings/
//     export-data. Outbound nav (file download). Enumerate, don't click.
//   - Section 05 / Billing — "Manage billing" button is permanently
//     `disabled` in the current build. Enumerate; click classifies as
//     DISABLED.
//   - Section 06 / Danger zone — DeleteAccountDialog trigger ("Delete
//     my account"). Opening the dialog is non-destructive (no DB
//     write), but the safer policy is to NOT click destructive
//     triggers at all — the dialog is gated behind a typed-DELETE +
//     password challenge, but we don't trust UI gates against the
//     possibility of a future regression that auto-confirms.
//   - AppFrame chrome (sidebar / top-bar / Cmd-K) — same as /dashboard;
//     handled as outbound nav for everything except in-page anchors.
//
// Per click target: snapshot `users` + `user_sessions` rows BEFORE/
// AFTER and compute audit-delta (auditTargetId=null because /settings
// is user-scoped, not visit-scoped — counts every recent audit row).
// Anchor-link clicks should produce zero diff in either table; a diff
// during navigation is a finding.
//
// Auth via lib/walker-base.mjs getOrCreateAuthState (session reuse —
// no per-walker login). Same /login-redirect retry shape as
// sweep-visit-page.mjs and sweep-dashboard.mjs.
//
// Usage:
//   node sweep-settings.mjs                 # default /settings
//   node sweep-settings.mjs --skip-clicks   # enumerate-only
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
    timeout: 15_000,
  };
  for (let i = 2; i < args.length; i += 1) {
    const a = args[i];
    if (a === '--base') { opts.base = args[i + 1]; i += 1; }
    else if (a === '--skip-clicks') { opts.skipClicks = true; }
    else if (a === '--timeout') { opts.timeout = Number(args[i + 1]); i += 1; }
    else if (a === '--help' || a === '-h') {
      stderr.write(
        'sweep-settings.mjs [--skip-clicks] [--timeout ms]\n'
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
const TARGET_URL = '/settings';

// ---------------------------------------------------------------------------
// Forbidden-button classifier
// ----------------------------------------------------------------------------
// Any element whose visible text or aria-label matches one of these
// patterns is enumerated but never clicked. The matching is case-
// insensitive and checked against the COMBINED label (text + aria) so
// renames don't trip the safety net.
//
// Each pattern carries a `risk` tag that surfaces in the
// click-skipped event so a Lead reviewer can see at a glance WHY the
// agent declined.
// ---------------------------------------------------------------------------

const FORBIDDEN_BUTTONS = [
  {
    pattern: /\bdelete\s+(my\s+)?account\b/i,
    risk: 'would-delete-qa-user',
    note: 'opens DeleteAccountDialog. Even though the dialog gates submission behind typed-DELETE + password, we do not trust UI gates against future regressions.',
  },
  {
    pattern: /\bsign\s+out\s+all(\s+devices)?\b/i,
    risk: 'kills-agent-session',
    note: 'signOutAllDevicesAction revokes every UserSession including the cached agent session.',
  },
  {
    pattern: /\brevoke\s+all\b/i,
    risk: 'kills-agent-session',
    note: 'mass session-revoke variant — same blast radius as "Sign out all devices".',
  },
  {
    pattern: /^\s*sign\s+out\s*$/i,
    risk: 'kills-agent-session',
    note: 'signOutAction destroys the current (cached) session; the next walker would face a /login redirect storm.',
  },
  {
    pattern: /\bupdate\s+password\b/i,
    risk: 'rotates-qa-password',
    note: 'POST /api/settings/change-password — would rotate the QA password to whatever we typed (or fail validation, but a future regression could weaken validation).',
  },
  {
    pattern: /\b(enable|disable)\s+(2fa|mfa|two-factor)\b/i,
    risk: 'mfa-lockout',
    note: 'enabling MFA without storing the recovery codes locks the QA user out of subsequent runs.',
  },
  {
    pattern: /\bmanage\s+billing\b/i,
    risk: 'outbound-stripe',
    note: 'would redirect to the Stripe customer portal. Currently `disabled` in the build, but the pattern stays in the safety net for when it ships.',
  },
  {
    pattern: /\bexport\s+my\s+data\b/i,
    risk: 'outbound-download',
    note: 'GET /api/settings/export-data triggers a file download — leaves the page and is unbounded in size (PHI export ZIP).',
  },
  {
    pattern: /\bsend\s+confirmation\b/i,
    risk: 'fires-real-email',
    note: 'ChangeEmailDialog submit fires a confirmation email to whatever address we typed.',
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
// DOM enumeration — same shape as sweep-dashboard.mjs.
// ---------------------------------------------------------------------------

async function enumerate(page) {
  return page.$$eval(
    'button, [role="button"], a[href], input[type="submit"]',
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

/** Decide whether an element's click would leave /settings. The six
 *  in-page anchor links (`#profile` … `#danger`) and other hash links
 *  stay in-page. Anything else with an off-page href is outbound. */
function isInPageAnchor(el) {
  if (el.tag !== 'a') return false;
  if (!el.href) return false;
  return el.href.startsWith('#');
}

function isOutbound(el) {
  if (el.tag !== 'a') return false;
  if (!el.href) return false;
  if (isInPageAnchor(el)) return false;
  if (el.href === '/settings') return false;
  if (el.href.startsWith('/settings?')) return false;
  if (el.href.startsWith('/settings#')) return false;
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
      name: 'settings',
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
    skippedDestructive: 0,
    skippedOutbound: 0,
    skippedDisabled: 0,
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

    // Baseline audit count. /settings is not visit-scoped. The page
    // load is largely a read; we don't expect a load-time audit row
    // (no VIEWED_SETTINGS exists in the AuditAction enum at the time
    // of writing). Anchor-link clicks should produce ZERO new audit
    // rows; a diff is a finding.
    const auditBaseline = snapshotAuditCount(null);
    emit({
      event: 'audit-baseline',
      url: TARGET_URL,
      count: auditBaseline,
      expected: [],
      note: 'no VIEWED_SETTINGS audit action exists; clean load expected.',
    });

    // Emit the forbidden-button safety net up-front so a Lead reading
    // the NDJSON sees the policy before the per-element stream.
    emit({
      event: 'safety-policy',
      walker: 'settings',
      forbiddenPatterns: FORBIDDEN_BUTTONS.map((f) => ({
        pattern: f.pattern.source,
        risk: f.risk,
      })),
    });

    const elements = await enumerate(page);
    counters.elements = elements.length;
    for (const el of elements) {
      // Pre-tag dangerous elements during enumeration so reviewers see
      // both the raw element and the safety classification in the
      // stream.
      const forbidden = forbiddenMatch(el.text || el.ariaLabel || '');
      emit({
        event: 'element',
        ...el,
        ...(forbidden
          ? { forbidden: true, risk: forbidden.risk }
          : {}),
      });
    }

    if (!opts.skipClicks) {
      // /settings's safe click surface (anchor links + ProfileForm
      // unchanged-save) should not mutate either of these tables. We
      // snapshot them anyway so the dbChanged signal flags any
      // unintended write during navigation.
      const dbSnapshotSpec = [
        {
          table: 'users',
          where: `email = '${(env.QA_AUDITOR_EMAIL ?? 'qa-auditor@quillmd.test').replace(/'/g, "''")}'`,
        },
        {
          table: 'user_sessions',
          where: `"userId" = (SELECT id FROM users WHERE email = '${(env.QA_AUDITOR_EMAIL ?? 'qa-auditor@quillmd.test').replace(/'/g, "''")}')`,
        },
      ];

      for (const el of elements) {
        const label = el.text || el.ariaLabel || `(${el.tag})`;

        // 1. FORBIDDEN — destructive button. Tag once, never click.
        const forbidden = forbiddenMatch(el.text || el.ariaLabel || '');
        if (forbidden) {
          emit({
            event: 'click-skipped',
            label,
            reason: 'destructive-not-clicked',
            risk: forbidden.risk,
            note: forbidden.note,
          });
          counters.skippedDestructive += 1;
          continue;
        }

        // 2. Disabled — enumerate but click would be a no-op anyway.
        //    Surface it as a skip rather than firing a click that
        //    classifies as DISABLED downstream.
        if (el.disabled) {
          emit({ event: 'click-skipped', label, reason: 'disabled' });
          counters.skippedDisabled += 1;
          continue;
        }

        // 3. Outbound nav (sidebar nav rows, "+ New visit", "Export
        //    my data" download). Enumerate; don't click — the
        //    forbidden-list above catches "Export my data"
        //    explicitly, but generic outbound links (sidebar
        //    /dashboard, /patients, /visits, brand link) land here.
        if (isOutbound(el)) {
          emit({
            event: 'click-skipped',
            label,
            reason: 'leaves-page',
            href: el.href,
          });
          counters.skippedOutbound += 1;
          continue;
        }

        // 4. Safe to click. Choose a selector spec and route through
        //    clickAndClassify. Anchor links use the href-attribute
        //    selector to disambiguate when sticky aside + section
        //    headings carry similar text.
        let selectorSpec;
        if (isInPageAnchor(el) && el.href) {
          selectorSpec = `a[href="${el.href}"]`;
        } else if (el.ariaLabel) {
          selectorSpec = {
            role: el.role ?? (el.tag === 'a' ? 'link' : 'button'),
            name: el.ariaLabel,
          };
        } else {
          selectorSpec = { text: label, exact: false };
        }

        const result = await clickAndClassify(page, {
          name: label,
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

        // Anchor-link clicks must NEVER mutate users / user_sessions.
        // A dbChanged=true here is a serious finding — surface it.
        if (isInPageAnchor(el) && result.dbChanged) {
          counters.findings += 1;
          emit({
            event: 'finding',
            label,
            kind: 'anchor-click-mutated-db',
            note: 'an in-page anchor click is supposed to be pure scroll; observed users/user_sessions diff.',
          });
        }

        emit({ event: 'click', label, ...result });

        // Re-navigate after each click for a stable starting state.
        // Anchor clicks change the URL hash, dialog triggers (e.g.
        // ChangeEmailDialog "Change") open Radix portals that would
        // shadow subsequent locator matches.
        await page.goto(TARGET_URL, {
          waitUntil: 'networkidle',
          timeout: opts.timeout,
        });
      }
    }

    emit({ event: 'sweep-end', ...counters });
    emit({
      event: 'walker-result',
      name: 'settings',
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
      name: 'settings',
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
