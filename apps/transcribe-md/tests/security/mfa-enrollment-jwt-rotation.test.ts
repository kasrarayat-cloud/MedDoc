// ============================================================================
// MFA enrollment revokes sibling sessions (Security Audit P1-J, 2026-05-13)
// ----------------------------------------------------------------------------
// Before this fix, flipping `mfaEnabled = true` left every existing
// session (other tabs / devices) untouched. "MFA-enabled" then no
// longer implied "this session passed an MFA challenge". The fix
// deletes every UserSession EXCEPT the current one inside the same
// transaction that flips the flag. If sessionId is unknown (legacy
// JWT), revoke ALL — correct-but-strict fallback.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const SRC = readFileSync(
  resolve(
    __dirname,
    '..',
    '..',
    'src',
    'app',
    'api',
    'mfa',
    'verify-enrollment',
    'route.ts',
  ),
  'utf-8',
);

describe('verify-enrollment — JWT rotation (P1-J)', () => {
  it('runs the MFA-flag update + session deleteMany in a single $transaction', () => {
    expect(SRC).toMatch(
      /prisma\.\$transaction\s*\(\s*\[[\s\S]*?prisma\.user\.update[\s\S]*?prisma\.userSession\.deleteMany/,
    );
  });

  it('reads sessionId from the current session for the KEEP-current branch', () => {
    // Reads (session?.user as any)?.sessionId — the JWT->session
    // wiring in packages/auth/src/index.ts:259 exposes sessionId
    // there. Cast to string|undefined for the deleteMany branch.
    expect(SRC).toMatch(
      /\.sessionId\s+as\s+[\s\S]*?string\s*\|\s*undefined/,
    );
  });

  it('deleteMany uses NOT: { sessionToken: currentSessionId } when sessionId present', () => {
    // The KEEP-current branch deletes every session whose
    // sessionToken does NOT match the current — keeps the user
    // logged in on the tab they just enrolled from.
    expect(SRC).toMatch(
      /currentSessionId[\s\S]*?NOT:\s*\{\s*sessionToken:\s*currentSessionId\s*\}/,
    );
  });

  it('falls back to deleting ALL sessions when sessionId is missing (legacy JWT path)', () => {
    // The else-branch passes `{ userId }` with no exclusion — every
    // session for the user is revoked. Strict-but-correct: a legacy
    // JWT without sessionId can't be safely preserved.
    expect(SRC).toMatch(
      /currentSessionId\s*\?\s*\{[\s\S]*?\}\s*:\s*\{\s*userId\s*\}/,
    );
  });

  it('audit metadata reports keptCurrentSession flag', () => {
    // Forensics distinguishes the legacy-fallback case (all
    // sessions revoked) from the standard case (current kept).
    expect(SRC).toMatch(/keptCurrentSession:\s*!!\s*currentSessionId/);
  });
});
