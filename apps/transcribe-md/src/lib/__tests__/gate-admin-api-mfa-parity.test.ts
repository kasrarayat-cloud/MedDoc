// ============================================================================
// THE ADMIN API GATE MUST ENFORCE MFA, BECAUSE THE ADMIN PAGE GATE DOES
// ----------------------------------------------------------------------------
// `app/admin/layout.tsx` requires MFA before any /admin/* PAGE renders, and its
// own comment says that closes shadow-audit HIPAA_FINDING_001.
// `lib/admin-api-gate.ts` did not check it at all — measured
// `grep -ci mfa admin-api-gate.ts` -> 0, positive-controlled against the page
// gate — so all 29 /api/admin/* endpoints, including the 12 POSTs that suspend,
// soft-delete, force-logout, reset passwords and grant or revoke SUPER_ADMIN,
// were reachable by a session the pages refuse.
//
// ⚠️ THE DEFECT IS NOT "NO MFA". IT IS TWO DOORS AND ONE LOCK. A control that
// holds on the surface people look at and not on the surface that performs the
// writes is worse than no control, because it reads as covered.
//
// ⚠️ WHY THIS GATE IS SOURCE-LEVEL AND SAYS SO. Driving `adminApi()` for real
// needs next-auth, a Prisma client and a NextRequest; those are integration
// concerns and this repo has no harness for them. What a source gate CAN do —
// and what an integration test would not do reliably — is fail the moment
// somebody removes the check, reorders it after the handler runs, or reads the
// flag from the JWT instead of the database. Each of those is an arm.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const SRC = path.resolve(__dirname, '../..');
const read = (rel: string) => readFileSync(path.join(SRC, rel), 'utf8');

/** Source with comments stripped — a rule must be CODE, not prose about code. */
const strip = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

const GATE = strip(read('lib/admin-api-gate.ts'));
const PAGE = strip(read('app/admin/layout.tsx'));

describe('admin API gate enforces MFA, at parity with the page gate', () => {
  it('POSITIVE CONTROL — the PAGE gate really does enforce MFA', () => {
    // If this ever stops being true the parity requirement is void and this
    // whole file is measuring a rule nobody holds. Without this arm the
    // assertions below could pass on a codebase where neither door checks.
    // ⚠️ WORD BOUNDARY, NOT A BARE SUBSTRING. Mutating the page gate's
    // `mfaEnabled` to `mfaEnabledXX` left `/mfaEnabled/` MATCHING — so this
    // control reported the page gate as intact while it had stopped enforcing
    // anything. Caught by mutation M6, in the one arm whose entire job is to
    // notice that. `\b` fails on `mfaEnabledXX` because `X` is a word character.
    expect(PAGE).toMatch(/\bmfaEnabled\b/);
    expect(PAGE).toMatch(/redirect\(/);
  });

  it('the API gate reads mfaEnabled and refuses when it is false', () => {
    expect(GATE, 'the API gate does not mention mfaEnabled at all').toMatch(/\bmfaEnabled\b/);
    // The refusal itself, not merely the field being selected: selecting a
    // column and never branching on it is the shape this arm exists to reject.
    expect(GATE, 'mfaEnabled is read but never refused on').toMatch(
      /if\s*\(\s*!\s*userRow\.mfaEnabled\s*\)\s*return\s+notFoundResponse\(\)/
    );
  });

  it('the flag is read FRESH FROM THE DATABASE, never from the session token', () => {
    // The page gate states the reason: enrolment happens in-session, so a
    // JWT-cached flag is stale exactly when it matters — the moment an operator
    // enrols in order to get back in.
    expect(GATE).toMatch(/select:\s*\{[^}]*\bmfaEnabled\b:\s*true/);
    // …and never off the session object.
    expect(GATE, 'mfaEnabled must not be read from the session/JWT').not.toMatch(
      /session[^\n]*\.mfaEnabled|u\.mfaEnabled/
    );
  });

  it('the refusal happens BEFORE the handler runs', () => {
    // A check that runs after `handler(req, …)` has already executed is not a
    // gate; the write has happened. Order is the property, so order is asserted.
    const refusal = GATE.indexOf('userRow.mfaEnabled');
    const handlerCall = GATE.indexOf('await handler(');
    expect(refusal, 'mfaEnabled check not found').toBeGreaterThan(-1);
    expect(handlerCall, 'handler invocation not found').toBeGreaterThan(-1);
    expect(refusal, 'the MFA refusal must precede the handler call').toBeLessThan(handlerCall);
  });

  it('it costs no extra query — mfaEnabled rides the row already being read', () => {
    // Two findUnique calls would be a real regression on every admin request.
    const finds = (GATE.match(/prisma\.user\.findUnique/g) ?? []).length;
    expect(finds, 'the gate should read the user row exactly once').toBe(1);
  });

  it('THE RECOVERY PATH STAYS OPEN — enrolment is not behind this gate', () => {
    // ⚠️ THE ARM THAT MAKES THE LOCKOUT SURVIVABLE. Production has 3 SUPER_ADMIN
    // accounts and 0 with MFA enrolled, so this change closes the admin API to
    // every one of them. That is only acceptable while they can still enrol.
    // If any of these routes were ever wrapped in `adminApi`, the lockout would
    // become permanent and unrecoverable from inside the product.
    for (const r of ['mfa/enroll', 'mfa/verify-enrollment', 'mfa/disable']) {
      const route = strip(read(`app/api/${r}/route.ts`));
      expect(route, `/api/${r} must NOT be admin-gated, or MFA lockout is permanent`)
        .not.toMatch(/adminApi/);
    }
  });
});
