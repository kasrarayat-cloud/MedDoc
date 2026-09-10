// ============================================================================
// Admin self-action guards (Security Audit P1-E, 2026-05-13)
// ----------------------------------------------------------------------------
// Three admin lifecycle routes (revoke-admin / suspend / soft-delete)
// already block actions where `id === ctx.session.user.id`. Four
// sibling routes — force-logout, reset-password, unsuspend,
// grant-admin — historically did not. The 4-route fix matches the
// existing guard shape; this source-pin test prevents regression.
//
// Pattern mirrors `tests/worker/worker-redact-phi.test.ts` (source-
// pin on a closed set) and `tests/audit/page-rsc-audits.test.ts`.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const REPO_ROOT = resolve(__dirname, '..', '..', '..', '..');

function readSource(rel: string): string {
  return readFileSync(resolve(REPO_ROOT, rel), 'utf-8');
}

/** Returns true iff the file contains a self-action guard near the
 *  top of the handler — the canonical pattern from
 *  `revoke-admin/route.ts:30-35`. The body has nested object
 *  literals (`{ error }`, `{ status: 403 }`) so a brace-class
 *  exclusion would break legitimate matches; instead, bound the
 *  match to a realistic byte distance (~400 chars) so an EMPTY
 *  guard body cannot match a far-away unrelated `status: 403`. */
function hasSelfActionGuard(src: string): boolean {
  return /if\s*\(\s*id\s*===\s*ctx\.session\.user\.id\s*\)\s*\{[\s\S]{20,400}?status:\s*403/.test(
    src,
  );
}

describe('Admin self-action guards (P1-E)', () => {
  it.each([
    ['revoke-admin', 'apps/transcribe-md/src/app/api/admin/users/[id]/revoke-admin/route.ts'],
    ['suspend', 'apps/transcribe-md/src/app/api/admin/users/[id]/suspend/route.ts'],
    ['soft-delete', 'apps/transcribe-md/src/app/api/admin/users/[id]/soft-delete/route.ts'],
    // The 4 new guards (this PR):
    ['force-logout', 'apps/transcribe-md/src/app/api/admin/users/[id]/force-logout/route.ts'],
    ['reset-password (admin)', 'apps/transcribe-md/src/app/api/admin/users/[id]/reset-password/route.ts'],
    ['unsuspend', 'apps/transcribe-md/src/app/api/admin/users/[id]/unsuspend/route.ts'],
    ['grant-admin', 'apps/transcribe-md/src/app/api/admin/users/[id]/grant-admin/route.ts'],
    // The console port (#310 step 3) — every ported door whose target can be
    // the actor is enrolled here in the same change that adds it.
    ['deactivate', 'apps/transcribe-md/src/app/api/admin/users/[id]/deactivate/route.ts'],
    ['reactivate', 'apps/transcribe-md/src/app/api/admin/users/[id]/reactivate/route.ts'],
    ['profile', 'apps/transcribe-md/src/app/api/admin/users/[id]/profile/route.ts'],
    ['sessions revoke', 'apps/transcribe-md/src/app/api/admin/users/[id]/sessions/[sid]/revoke/route.ts'],
  ])('%s blocks self-target with 403', (_name, path) => {
    expect(hasSelfActionGuard(readSource(path))).toBe(true);
  });
});
