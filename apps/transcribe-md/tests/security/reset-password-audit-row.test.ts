// ============================================================================
// Reset-password emits PASSWORD_CHANGED (Security Audit P1-A, 2026-05-13)
// ----------------------------------------------------------------------------
// HIPAA §164.312(b) requires credential-material change events to be
// logged regardless of trigger. `/api/settings/change-password`
// already emits PASSWORD_CHANGED; `/api/auth/reset-password` (the
// token-redemption path) was the missing case. Source-pin so future
// edits can't silently drop the audit emit.
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
    'auth',
    'reset-password',
    'route.ts',
  ),
  'utf-8',
);

describe('reset-password — PASSWORD_CHANGED audit (P1-A)', () => {
  it("imports logAudit from '@/lib/audit'", () => {
    expect(SRC).toMatch(
      /import\s+\{\s*logAudit\s*\}\s+from\s+['"]@\/lib\/audit['"]/,
    );
  });

  it('emits PASSWORD_CHANGED tagged via=reset_token after the transaction', () => {
    // Whitespace-flexible to survive prop reordering. Must include
    // both `action: 'PASSWORD_CHANGED'` AND `via: 'reset_token'`
    // (distinguishes from change-password's same-action emit).
    expect(SRC).toMatch(
      /logAudit\s*\(\s*\{[\s\S]*?action:\s*['"]PASSWORD_CHANGED['"][\s\S]*?via:\s*['"]reset_token['"]/,
    );
  });

  it('passes targetId + userId override from the consumed token', () => {
    // The reset endpoint runs WITHOUT an active session (user proved
    // ownership via the token, hasn't signed in yet). The logAudit
    // call must explicitly pass userId so the row isn't attributed
    // to a null/sentinel userId.
    expect(SRC).toMatch(
      /logAudit\s*\(\s*\{[\s\S]*?userId:\s*consumed\.userId/,
    );
  });
});
