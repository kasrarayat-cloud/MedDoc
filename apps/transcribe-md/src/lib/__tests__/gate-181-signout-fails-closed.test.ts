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
import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const APP = join(__dirname, '..', '..', '..');
const REPO = join(APP, '..', '..');
const read = (p: string) => readFileSync(join(REPO, p), 'utf8');

const SHARED_AUTH = 'packages/auth/src/index.ts';
const ACTION = 'apps/transcribe-md/src/actions/session.ts';

describe('#182(3) — every sign-out door, ENUMERATED FROM THE TREE', () => {
  // ⚠️ THE LIST IS GREPPED, NOT AUTHORED, AND THAT CHANGE IS THE FINDING.
  // The previous version hard-coded four paths — the four the fix had touched —
  // and was 12/12 GREEN while TWO live doors ignored the result, one of them
  // `command-palette.tsx`, mounted in the ROOT LAYOUT and reachable by Cmd+K on
  // every page. The adversarial pass found both; this gate could not, because a
  // hand-written watched set can only ever contain what its author already knew.
  //
  // A door that appears tomorrow is watched tomorrow, with no edit here.
  const doors = execSync(
    "grep -rl 'signOutAction\\|signOutAllDevicesAction' apps/transcribe-md/src " +
      "--include='*.tsx' --include='*.ts' | grep -v '__tests__' | grep -v 'actions/session.ts'",
    { cwd: REPO, encoding: 'utf8' },
  )
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean);

  it('NON-VACUITY: the enumeration finds a plausible number of doors', () => {
    // If the grep breaks, it returns nothing and every arm below passes over an
    // empty set — the exact vacuity this gate was rewritten to escape.
    expect(doors.length, 'the door enumeration found nothing — the arms are vacuous').toBeGreaterThanOrEqual(5);
    expect(doors.some((d) => d.includes('command-palette'))).toBe(true);
    expect(doors.some((d) => d.includes('user-menu'))).toBe(true);
  });

  it('NO door imports signOut from next-auth/react', () => {
    for (const d of doors) {
      expect(read(d), `${d} is back on the CSRF-gated client POST`).not.toMatch(
        /from\s+['"]next-auth\/react['"]/,
      );
    }
  });

  it('every door BINDS the result and BRANCHES on it — not `.ok` somewhere in the file', () => {
    // ⚠️ THE OLD ARM MATCHED /\.ok/ ANYWHERE, so an unrelated `res.ok` from a
    // fetch elsewhere in the same file satisfied it. It was already vacuous for
    // delete-account-dialog.tsx on the day it was written.
    for (const d of doors) {
      const src = read(d);
      const m = /(?:const|let)\s+(\w+)\s*=\s*await\s+signOut(?:AllDevices)?Action\s*\(/.exec(src);
      expect(m, `${d} does not BIND the SignOutResult — it discards it`).not.toBeNull();
      const name = m![1];
      expect(
        new RegExp(`if\\s*\\(\\s*!\\s*${name}\\.ok`).test(src),
        `${d} binds the result but never branches on ${name}.ok`,
      ).toBe(true);
    }
  });

  it('every door RENDERS the failure — a branch that returns silently is the same bug', () => {
    for (const d of doors) {
      const src = read(d);
      expect(
        /toast\.error|setSignOutError|setError|role="alert"/.test(src),
        `${d} branches on failure but shows the doctor nothing`,
      ).toBe(true);
    }
  });

  it('the action returns a FAILURE VALUE and never reports unconfirmed success', () => {
    const src = read(ACTION);
    expect(src).toContain('ok: false');
    expect(src).toContain('SIGNOUT_REVOKE_FAILED');
    // #182(2) — an unresolvable session id is a FAILURE, not a silent skip
    expect(src).toContain('session id unresolvable');
    // and every attempt leaves a receipt, with its outcome
    expect(src).toContain('recordLogoutAttempt');
    expect(src).toMatch(/recordLogoutAttempt\('FAILED'/);
    expect(src).toMatch(/recordLogoutAttempt\('SUCCESS'/);
    expect(src, 'the old guard that fell through to success is back').not.toMatch(
      /if \(sessionId\) \{\s*try \{\s*await revokeSession/,
    );
  });

  it('⚠️ the meddoc-pro app is OUT OF SCOPE, recorded rather than silently skipped', () => {
    // The pass found two client sign-out surfaces in apps/meddoc-pro still on
    // the CSRF-gated path. That app is being deleted, so they are not fixed —
    // but "not fixed" and "not noticed" must not look the same in the record.
    // This arm exists so the exclusion is a written decision with an owner.
    expect(doors.every((d) => d.startsWith('apps/transcribe-md/'))).toBe(true);
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

  it('(d)/#182(1) a validateSession throw is CANNOT-TELL: marked, not null, and loud', () => {
    // ⚠️ THE RETURN IS ASSERTED BEHAVIOURALLY IN gate-182-session-fails-closed,
    // which CALLS the callback. This arm only pins the shape that arm depends
    // on. The previous version of this arm asserted LOG TEXT alone, and the
    // adversarial pass showed it stayed green while the pre-fix pass-through
    // was restored verbatim — a rule about a RETURN cannot be tested by reading
    // a string.
    expect(src).toContain('SESSION_UNVERIFIABLE');
    expect(src).toContain('sessionVerifyFailed');
    expect(src, 'the #181(d) null-on-throw is back — it clears the cookie on a blip').not.toContain(
      'treated as INVALID and the JWT is REJECTED',
    );
    expect(src, 'the original fail-open wording is back').not.toContain('the JWT was honoured.');
  });

  it('(e) a token with no sessionId is REJECTED, not waved through as legacy', () => {
    expect(src).toContain('SESSION_NO_ID');
    expect(src, 'the legacy pass-through is back').not.toContain(
      'they pass\n      // through until their natural JWT expiry',
    );
  });

  it('⚠️ the reserved isActive fail-open is SETTLED the same way — #182(1)', () => {
    // It served a deactivated, suspended or soft-deleted account from JWT
    // claims when its lookup threw, under a comment saying the trade was "a
    // war-room ruling, not a code decision — it is pending". The ruling came.
    const appAuth = read('apps/transcribe-md/src/lib/auth.ts');
    expect(appAuth, 'the fail-open still serves JWT-claimed values').not.toContain(
      'serving JWT-claimed values',
    );
    expect(appAuth).toContain('SessionUnverifiableError');
    // and the per-query argument is KEPT, because it is what makes ejecting on
    // a blip wrong as well — both directions were wrong, in that order
    expect(appAuth).toContain('PER-QUERY under load');
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
