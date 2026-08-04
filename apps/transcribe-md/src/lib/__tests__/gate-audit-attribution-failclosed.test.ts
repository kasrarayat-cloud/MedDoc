// ============================================================================
// An audit write with no practice in scope must FAIL CLOSED.
// ----------------------------------------------------------------------------
// ⚠️ THIS EXISTS BECAUSE THE TENANT BOUNDARY FAILED **OPEN**, IN PRODUCTION,
// FOR MONTHS.
//
// Until 2026-08-04 `logAudit` resolved the tenant as:
//
//     input.practiceId ?? sessionPracticeId ?? 'clinic_main'
//
// so any write with no practice in scope was attributed to `clinic_main` —
// the largest SHARED practice in production (11 users). Measured the day it
// was found: **64 `LOGOUT` rows**, from 64 different solo doctors, every one
// filed under Main Clinic. Under the practice-scoped audit views the
// FOUNDATION spec calls for, each of those doctors' sign-outs would have been
// readable by a practice they have never belonged to.
//
// The failure mode is the thing to keep in mind, not the constant: a boundary
// whose behaviour on UNKNOWN input is "assume the biggest tenant" is the exact
// inverse of a boundary. Unknown must mean unknown.
//
// WHAT WOULD MAKE THIS GATE FAIL (and it has been made to fail, deliberately,
// against the pre-fix source — see the mutation block at the bottom):
//   • re-introducing any `?? '<literal>'` tenant fallback in logAudit
//   • writing the sentinel into `practiceId` (an FK) instead of the snapshot
//   • dropping the loud console.error, so an UNATTRIBUTED row goes out quietly
//   • letting the whole file stop parsing, which would make every assertion
//     below vacuously true — hence the non-vacuity test first
// ============================================================================

import { readFileSync } from 'node:fs';

import { describe, it, expect } from 'vitest';

const SRC = readFileSync('src/lib/audit.ts', 'utf8');

/** `SRC` with comments stripped. Every assertion runs against THIS, because
 *  this file's own prose quotes `?? 'clinic_main'` verbatim — a naive grep
 *  over the raw source would match the explanation and report the bug it is
 *  explaining. (The same trap cost a round on the R2 sign-bar guard.) */
const CODE = SRC.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

/** The body of `logAudit`, comments stripped — the only region that matters. */
function logAuditBody(): string {
  const start = CODE.indexOf('export async function logAudit');
  expect(start, 'logAudit not found — has it been renamed?').toBeGreaterThan(-1);
  return CODE.slice(start);
}

describe('audit attribution fails CLOSED', () => {
  it('NON-VACUITY — the source parsed to something real', () => {
    // Without this, a file that failed to read (or a comment-stripper that ate
    // everything) would make every assertion below trivially true, and the
    // gate would report green about nothing at all.
    expect(CODE.length, 'audit.ts stripped to (almost) nothing').toBeGreaterThan(2000);
    expect(CODE).toContain('export async function logAudit');
    expect(logAuditBody().length).toBeGreaterThan(500);
  });

  it('there is NO literal practice fallback anywhere in logAudit', () => {
    const body = logAuditBody();
    // The specific historical value...
    expect(
      body,
      "the `?? 'clinic_main'` fail-open is back — see this file's header for " +
        'what it cost',
    ).not.toContain('clinic_main');
    // ...and the shape, so the next one is caught even under a new name.
    // Matches `?? 'anything'` / `|| "anything"` on the practice resolution.
    const fallbacks = [...body.matchAll(/practiceId[\s\S]{0,120}?(\?\?|\|\|)\s*['"`][^'"`]+['"`]/g)];
    expect(
      fallbacks.map((m) => m[0].replace(/\s+/g, ' ')),
      'a STRING-literal tenant fallback was reintroduced. The tenant is ' +
        'either known or it is null; there is no third answer, and inventing ' +
        'one silently mis-files another practice\'s rows.',
    ).toEqual([]);
  });

  it('the resolution ends in null, not in a value', () => {
    expect(logAuditBody()).toMatch(
      /const practiceId\s*=\s*input\.practiceId\s*\?\?\s*sessionPracticeId\s*\?\?\s*null;/,
    );
  });

  it('an unresolvable tenant is reported LOUDLY, not swallowed', () => {
    const body = logAuditBody();
    expect(body).toMatch(/if \(practiceId === null\)/);
    // console.error, not warn or log: this is a caller defect, and a warning
    // in a stream nobody reads is the same as no signal at all.
    const guard = body.slice(body.indexOf('if (practiceId === null)'));
    expect(guard.slice(0, 600)).toContain('console.error');
    expect(guard.slice(0, 600)).toContain('UNATTRIBUTED');
  });

  it('the sentinel goes in the SNAPSHOT column, never in the FK column', () => {
    const body = logAuditBody();
    // practiceId is an FK to `practices`. A sentinel there either violates the
    // constraint or forces a fake Practice row into every count in the product.
    expect(body).toMatch(/practiceIdSnapshot:\s*practiceId\s*\?\?\s*UNATTRIBUTED_PRACTICE/);
    expect(body).toMatch(/^\s*practiceId,\s*$/m);
    expect(body).not.toMatch(/practiceId:\s*UNATTRIBUTED_PRACTICE/);
  });

  it('the sentinel is exported so callers and repair scripts share ONE spelling', () => {
    expect(CODE).toMatch(/export const UNATTRIBUTED_PRACTICE = 'UNATTRIBUTED';/);
  });

  it('POSITIVE CONTROL — these matchers really do fire on the pre-fix source', () => {
    // The mutation this gate was proven against: the exact line as it stood
    // before 2026-08-04. If the assertions above were written loosely enough
    // to pass on this, the gate would be decoration.
    const preFix = `
      export async function logAudit(input) {
        const practiceId =
          input.practiceId ?? sessionPracticeId ?? 'clinic_main';
        const entry = { practiceId, practiceIdSnapshot: practiceId };
      }
    `;
    expect(preFix).toContain('clinic_main');
    expect(
      [...preFix.matchAll(/practiceId[\s\S]{0,120}?(\?\?|\|\|)\s*['"`][^'"`]+['"`]/g)].length,
      'the fallback-shape matcher does not fire on the very source it was ' +
        'written to catch — it would pass on the bug',
    ).toBeGreaterThan(0);
    expect(preFix).not.toMatch(/if \(practiceId === null\)/);
    expect(preFix).not.toMatch(
      /practiceIdSnapshot:\s*practiceId\s*\?\?\s*UNATTRIBUTED_PRACTICE/,
    );
  });
});

describe('the contextless callers thread the tenant by traversal', () => {
  const NEXTAUTH = readFileSync('src/lib/nextauth.ts', 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '');

  it('signOut resolves the practice before writing LOGOUT', () => {
    // `auth()` cannot run inside the signOut event — it is outside request
    // scope — so logAudit's own resolution returns null there. 64 production
    // rows are the evidence. One primary-key lookup is the fix.
    expect(NEXTAUTH).toMatch(/prisma\.user\.findUnique\(\{[\s\S]{0,200}?practiceId:\s*true/);
    expect(NEXTAUTH).toMatch(
      /logAudit\(\{\s*action:\s*'LOGOUT',\s*userId,\s*practiceId\s*\}\)/,
    );
  });

  it('POSITIVE CONTROL — the LOGOUT matcher fails on the pre-fix call', () => {
    expect(`void logAudit({ action: 'LOGOUT', userId });`).not.toMatch(
      /logAudit\(\{\s*action:\s*'LOGOUT',\s*userId,\s*practiceId\s*\}\)/,
    );
  });
});
