// ============================================================================
// #181 — SIGN-OUT FAILS CLOSED, AND A SESSION THAT CANNOT BE VALIDATED IS INVALID
// ----------------------------------------------------------------------------
// ⚠️ THE DEFECT, TRACED END TO END BEFORE A LINE WAS CHANGED. A doctor clicked
// Sign out; the server answered 200; the session stayed live for the remaining
// 7 days of the JWT's maxAge; no LOGOUT audit row was written; and the UI
// bounced back to /board looking exactly like a normal session.
//
// `events.signOut` — which holds BOTH the `revokeSession` call and the audit
// row — is reachable ONLY from `actions.signOut`, and `@auth/core/lib/index.js`
// gates that on CSRF first:
//
//     case "signout":
//         validateCSRF(action, csrfTokenVerified);
//         return await actions.signOut(cookies, sessionStore, options);
//
// The trigger needs no race: `getCsrfToken()` in `next-auth/react` ends
// `return response?.csrfToken ?? ""`, so ONE transient blip on the preceding GET
// silently produces an unverifiable POST. The 200 comes from the client always
// sending `X-Auth-Return-Redirect: 1`, which makes the framework's error path
// answer `Response.json({ url })` — 200, and no Set-Cookie at all.
//
// ⚠️ EVERY ONE OF THOSE LINKS WAS READ IN `node_modules` FIRST-HAND. A chain
// this long assembled from memory would be a story; assembled from the files it
// is a mechanism.
//
// WHAT THIS GATE WATCHES — the four fail-closed properties, each of which was
// fail-OPEN before:
//
//   (a)/(b) every client sign-out door goes through the SERVER ACTION, so there
//           is no NextAuth CSRF token to lose and no 200 that means nothing
//   (c)     a sign-in whose UserSession insert fails REFUSES, rather than
//           minting a token with no sessionId that nothing could ever revoke
//   (d)     a validateSession throw is INVALID, not a pass-through
//   (e)     a token carrying no sessionId at all is REJECTED
// ============================================================================
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const APP = join(__dirname, '..', '..', '..');
const REPO = join(APP, '..', '..');
const read = (p: string) => readFileSync(join(REPO, p), 'utf8');

const SHARED_AUTH = 'packages/auth/src/index.ts';
const ACTION = 'apps/transcribe-md/src/actions/session.ts';

describe('#181 (a)/(b) — every client sign-out door is the server action', () => {
  // ⚠️ THE DOORS ARE ENUMERATED FROM THE TREE, NOT FROM MEMORY. Hardening the
  // account menu alone would have left the admin overview and the
  // delete-account dialog on the broken path — the bug was REPORTED from one
  // surface and lived on three.
  const DOORS = [
    'apps/transcribe-md/src/components/rounds/account-menu.tsx',
    'apps/transcribe-md/src/app/admin/_components/AdminOverview.client.tsx',
    'apps/transcribe-md/src/app/settings/delete-account-dialog.tsx',
    'apps/transcribe-md/src/app/settings/session-panel.tsx',
  ];

  it('NON-VACUITY: every enumerated door exists and mentions signing out', () => {
    for (const d of DOORS) {
      const src = read(d);
      expect(src.length, `${d} is empty`).toBeGreaterThan(200);
      expect(src.toLowerCase(), `${d} does not sign out at all`).toMatch(/sign\s?out/i);
    }
  });

  it('NO client surface imports signOut from next-auth/react', () => {
    for (const d of DOORS) {
      expect(read(d), `${d} still calls the CSRF-gated client POST`).not.toContain(
        "from 'next-auth/react'",
      );
    }
  });

  it('every door calls signOutAction and CHECKS the result', () => {
    for (const d of DOORS) {
      const src = read(d);
      expect(src, `${d} does not use the hardened action`).toMatch(
        /signOutAction|signOutAllDevicesAction/,
      );
      // ⚠️ CALLING IT IS NOT CHECKING IT. `settings/session-panel.tsx` used to
      // `await signOutAction()` and then announce "Signed out" unconditionally
      // — a success message asserted rather than observed.
      expect(src, `${d} ignores the result`).toMatch(/\.ok|result\.ok|signedOut\.ok/);
    }
  });

  it('the action returns a FAILURE VALUE rather than throwing or redirecting', () => {
    const src = read(ACTION);
    expect(src).toContain('ok: false');
    expect(src).toContain('SIGNOUT_REVOKE_FAILED');
    // and it must not swallow the revoke the way it used to
    expect(src, 'the revoke failure is swallowed again').not.toContain(
      'revokeSession(sessionId).catch(() => {',
    );
  });
});

describe('#181 (c)(d)(e) — the shared jwt callback fails closed', () => {
  const src = read(SHARED_AUTH);

  it('NON-VACUITY: the callback and its three branches are present', () => {
    expect(src).toContain('async jwt(');
    expect(src).toContain('recordSessionLogin');
    expect(src).toContain('validateSession');
  });

  it('(c) a failed UserSession insert REFUSES the sign-in — the fail-open line is gone', () => {
    // ⚠️ ASSERTED ON THE BEHAVIOUR, NOT ON THE ABSENCE OF PROSE. The first
    // version of this arm forbade the old comment's text — and then FIRED on
    // the new comment, which quotes that text while explaining its removal. A
    // source-text rule cannot tell a quotation from the thing quoted, so it was
    // moved onto the code: the sign-in catch must THROW.
    expect(src).toContain('SESSION_TRACKING_FAILED');
    const signInCatch = src.slice(
      src.indexOf('UserSession record on sign-in failed'),
      src.indexOf('// ── Subsequent-request path'),
    );
    expect(signInCatch.length, 'the sign-in catch block was not located').toBeGreaterThan(80);
    expect(signInCatch, 'the sign-in catch swallows the failure again').toContain('throw new Error(');
  });

  it('(d) a validateSession throw is INVALID, and stays observable', () => {
    // the log is KEPT — it is what made the ruling possible — but the RETURN moved
    expect(src).toContain('SESSION_FAILOPEN');
    expect(src).toContain('treated as INVALID and the JWT is REJECTED');
    expect(src, 'the old pass-through wording is back').not.toContain(
      'the JWT was honoured.',
    );
  });

  it('(e) a token with no sessionId is REJECTED, not waved through as legacy', () => {
    expect(src).toContain('SESSION_NO_ID');
    expect(src, 'the legacy pass-through is back').not.toContain(
      'they pass\n      // through until their natural JWT expiry',
    );
  });

  it('⚠️ the justification does not claim a DB outage makes the product unusable', () => {
    // That claim was in an earlier draft and is FALSE: PRISMA_POOL_MAX=10 with a
    // 20s pool timeout makes failures PER-QUERY, so this lookup can time out
    // while clinical queries succeed. A comment that argues from a false premise
    // is how the next reader talks themselves back into the fail-open.
    expect(src).toContain('PER-QUERY UNDER LOAD');
    expect(src).not.toContain('The availability we were protecting does not exist');
  });
});

describe('#181/1 — the shipped commit is stamped into the images', () => {
  it('both Dockerfiles carry the OCI revision label', () => {
    for (const f of ['apps/transcribe-md/Dockerfile', 'apps/transcribe-md/Dockerfile.worker']) {
      const src = read(f);
      expect(src, `${f} has no revision ARG`).toContain('ARG GIT_REVISION');
      expect(src, `${f} has no OCI label`).toContain('org.opencontainers.image.revision');
    }
  });

  it('compose passes it to BOTH services, defaulting to `unknown`', () => {
    const compose = read('docker-compose.yml');
    // ⚠️ `unknown` rather than empty: a local build must never silently claim
    // to be a commit it is not.
    expect(compose).toContain('GIT_REVISION: ${GIT_REVISION:-unknown}');
    expect(compose.match(/GIT_REVISION: \$\{GIT_REVISION:-unknown\}/g)?.length).toBe(2);
  });

  it('the deploy EXPORTS it — an arg compose cannot read is not wired', () => {
    const deploy = read('scripts/deploy-prod.sh');
    expect(deploy).toContain('GIT_REVISION="$(git rev-parse HEAD)"');
    expect(deploy, 'set but not exported — compose reads the environment').toContain(
      'export GIT_REVISION',
    );
  });
});
