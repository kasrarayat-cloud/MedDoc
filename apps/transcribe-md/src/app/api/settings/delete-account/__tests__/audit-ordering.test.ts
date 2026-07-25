// ============================================================================
// S4c regression guard — the ACCOUNT_DELETED row must be written BEFORE the
// destructive transaction, and must be awaited.
// ----------------------------------------------------------------------------
// The shipped bug was an ordering bug, not a missing call. `void logAudit(...)`
// sat AFTER the $transaction, which meant:
//
//   1. the transaction always threw (audit_logs.practiceId was ON DELETE
//      RESTRICT, so DELETE practices was refused), the handler returned 500
//      from the catch, and the audit line was never reached at all; and
//   2. even on the success path it passed practiceId — a row that no longer
//      existed by then — so the INSERT would have failed the FK check, and
//      `void` would have swallowed that failure silently.
//
// Both are invisible to a green typecheck and to any test that only asserts
// "logAudit is called somewhere". Ordering is the property that matters, so
// ordering is what this asserts.
// ============================================================================

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const raw = readFileSync(join(__dirname, '..', 'route.ts'), 'utf-8');
// Strip comments — the header above quotes the buggy form verbatim, and so
// does the route's own explanatory comment.
const src = raw.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

describe('delete-account — audit ordering', () => {
  it('writes ACCOUNT_DELETED before the destructive transaction', () => {
    const audit = src.indexOf("action: 'ACCOUNT_DELETED'");
    const txn = src.indexOf('prisma.$transaction');
    expect(audit, 'ACCOUNT_DELETED is not written at all').toBeGreaterThan(-1);
    expect(txn, 'no destructive transaction found').toBeGreaterThan(-1);
    expect(
      audit,
      'ACCOUNT_DELETED is written AFTER the transaction — it will reference a ' +
        'practice that no longer exists, and will never run at all if the ' +
        'transaction throws'
    ).toBeLessThan(txn);
  });

  it('awaits the audit write instead of firing it into the void', () => {
    expect(
      src,
      'the audit write is fire-and-forget; an FK violation or a dead DB would ' +
        'be swallowed and the account deleted with no record'
    ).toMatch(/await logAudit\(\{\s*\n\s*action: 'ACCOUNT_DELETED'/);
    expect(src).not.toMatch(/void logAudit\(\{\s*\n\s*action: 'ACCOUNT_DELETED'/);
  });

  it('deletes the user before the practice', () => {
    // The practice delete nulls audit/billing refs. The user delete cascades
    // visits. Reversing them reintroduces a RESTRICT failure via users.practiceId.
    const u = src.indexOf('tx.user.delete');
    const p = src.indexOf('tx.practice.delete');
    expect(u).toBeGreaterThan(-1);
    expect(p).toBeGreaterThan(u);
  });

  it('never deletes audit_logs or billing_events', () => {
    // These DETACH via ON DELETE SET NULL. If anyone ever "fixes" a future FK
    // error by deleting them here, the append-only guarantee is gone.
    expect(src).not.toMatch(/auditLog\.deleteMany/);
    expect(src).not.toMatch(/billingEvent\.deleteMany/);
  });
});
