// ============================================================================
// S4c regression guard — the ACCOUNT_DELETED row: written while its references
// are valid, fail-closed, and (ADMIN-5) sharing the transaction's fate.
// ----------------------------------------------------------------------------
// The shipped S4c bug was an ordering bug, not a missing call. `void logAudit(...)`
// sat AFTER the $transaction, which meant:
//
//   1. the transaction always threw (audit_logs.practiceId was ON DELETE
//      RESTRICT, so DELETE practices was refused), the handler returned 500
//      from the catch, and the audit line was never reached at all; and
//   2. even on the success path it passed practiceId — a row that no longer
//      existed by then — so the INSERT would have failed the FK check, and
//      `void` would have swallowed that failure silently.
//
// S4c's cure was "audit FIRST, awaited, outside the transaction".
//
// ⚠️ ADMIN-5 (2026-09-10) — THAT CURE HAD A THIRD OUTCOME NOBODY PINNED. A row
// written before and outside the transaction SURVIVES a deletion the database
// refuses (the last-owner trigger; the users->practices FK), so the append-only
// trail said an account was deleted that still existed. Measured on a real
// database: 500, one ACCOUNT_DELETED row, the user intact. The row is now
// BUILT before the transaction (fail-closed) and WRITTEN as the transaction's
// first statement (valid references, and it rolls back with the deletion).
//
// ⚠️ THESE ARMS READ SOURCE ORDER, AND RULING #251 RETIRES TEXT SCANNERS AS
// PROOFS OF BEHAVIOUR. They are the cheap tripwire. The behaviour is DRIVEN in
// `admin5-member-deletion.test.ts` (mocked transaction) and in
// `src/lib/__tests__/admin5-db-proofs.db.test.ts` (a real Postgres).
// ============================================================================

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const raw = readFileSync(join(__dirname, '..', 'route.ts'), 'utf-8');
// Strip comments — the header above quotes the buggy forms verbatim, and so
// does the route's own explanatory comment.
const src = raw.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

describe('delete-account — audit ordering', () => {
  it('BUILDS the ACCOUNT_DELETED row before the destructive transaction (fail-closed)', () => {
    const build = src.indexOf('await buildAuditRow({');
    const txn = src.indexOf('prisma.$transaction');
    expect(build, 'the ACCOUNT_DELETED row is not built at all').toBeGreaterThan(-1);
    expect(txn, 'no destructive transaction found').toBeGreaterThan(-1);
    expect(build).toBeLessThan(txn);
    expect(src.slice(build, txn)).toMatch(/action: 'ACCOUNT_DELETED'/);
  });

  it('⚠️ WRITES it INSIDE the transaction, before any destructive statement', () => {
    const txn = src.indexOf('prisma.$transaction');
    const write = src.indexOf('tx.auditLog.create');
    expect(write, 'the row is not written inside the transaction').toBeGreaterThan(txn);
    for (const later of ['tx.accountDeletion.create', 'tx.user.delete', 'tx.patient.deleteMany', 'tx.practice.delete']) {
      expect(write, `${later} runs before the audit row`).toBeLessThan(src.indexOf(later));
    }
  });

  it('⚠️ never writes ACCOUNT_DELETED through logAudit — the out-of-transaction writer that survived a rollback', () => {
    expect(src).not.toMatch(/logAudit\(\{\s*\n\s*action: 'ACCOUNT_DELETED'/);
  });

  it('ADMIN-5 — the membership refusal precedes the audit build and the transaction', () => {
    const refusal = src.indexOf("code: 'PRACTICE_HAS_MEMBERS'");
    expect(refusal).toBeGreaterThan(-1);
    expect(refusal).toBeLessThan(src.indexOf('await buildAuditRow({'));
    expect(refusal).toBeLessThan(src.indexOf('prisma.$transaction'));
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
