// ============================================================================
// ADMIN-5 — the last-owner guard's STRUCTURE, and the ratchet that keeps it the
// only door.
// ----------------------------------------------------------------------------
// ⚠️ WHAT THIS FILE CANNOT PROVE, SAID FIRST SO NOTHING HERE IS READ AS MORE
// THAN IT IS.
//
// The guard's correctness is a CONCURRENCY property, and this harness cannot
// produce an interleaving: `@meddoc/db` is mocked in every arm below, and the
// transcribe-md unit suite has no database at all (the CI `unit` job declares
// no `services:` block). A green run here is consistent with a guard that
// deadlocks, that never takes its lock, or whose SQL does not parse.
//
// The concurrency proof is `tests/e2e/scenarios/40-admin5-last-owner.spec.ts`,
// which races the SHIPPED statements — imported from
// `practice-owner-guard-sql`, not retyped — against the real Postgres in the QA
// stack, with a NEGATIVE CONTROL that must leave zero owners.
//
// What this file proves is the half that a real-database test cannot see
// cheaply: the SHAPE of the statements, and that no second door exists.
// ============================================================================

import { describe, expect, it, vi } from 'vitest';

import {
  CHANGE_ROLE_GUARDED_SQL,
  LAST_OWNER_CLAUSE,
  PRACTICE_LOCK_SQL,
  PROMOTE_SQL,
  REMOVE_MEMBER_GUARDED_SQL,
} from '../practice-owner-guard-sql';

describe('⚠️ the statements carry the guard, and the guard is INSIDE them', () => {
  it('the demotion statement carries the last-owner clause; the promotion one does NOT', () => {
    expect(CHANGE_ROLE_GUARDED_SQL).toContain(LAST_OWNER_CLAUSE);
    // ⚠️ THE NEGATIVE HALF IS THE ONE WORTH HAVING. A clause on the promotion
    // path would refuse a solo owner minting a second one — the exact move a
    // practice makes to become safe — and it would refuse it for want of the
    // owner it is about to create.
    expect(PROMOTE_SQL).not.toContain(LAST_OWNER_CLAUSE);
    expect(PROMOTE_SQL).not.toMatch(/count\(\*\)/);
  });

  it('⚠️ REMOVAL CARRIES THE SAME CLAUSE — the second door to one invariant', () => {
    // Removing the last owner strands a practice exactly as demoting them does.
    // A guard fitted only to the role change looks complete and is not.
    expect(REMOVE_MEMBER_GUARDED_SQL).toContain(LAST_OWNER_CLAUSE);
    // and removal must NULL the role, which is what makes it a demoting write
    expect(REMOVE_MEMBER_GUARDED_SQL).toMatch(/"practiceRole"\s*=\s*NULL/);
  });

  it('the count is inside the WHERE, never a statement of its own', () => {
    // ⚠️ THE ADMIN-5 ROW FORBIDS "a count read and then acted on". The
    // discriminator is not that a count exists — it is WHERE it exists. A
    // `SELECT count(*)` that is its own statement is the forbidden shape; the
    // same text inside an UPDATE's WHERE is the required one.
    for (const sql of [CHANGE_ROLE_GUARDED_SQL, REMOVE_MEMBER_GUARDED_SQL]) {
      expect(sql.trimStart()).toMatch(/^UPDATE users/);
      const beforeWhere = sql.slice(0, sql.indexOf('WHERE'));
      expect(beforeWhere).not.toMatch(/count\(\*\)/);
      expect(sql.slice(sql.indexOf('WHERE'))).toMatch(/count\(\*\)/);
    }
  });

  it('⚠️ the clause uses IS DISTINCT FROM, because practiceRole is NULLABLE', () => {
    // `NULL <> 'OWNER'` is NULL, not TRUE — so a plain `<>` would make the whole
    // conjunction NULL and refuse every change to a member whose role is NULL.
    // That is the row a removed-then-readded member carries.
    expect(LAST_OWNER_CLAUSE).toContain('IS DISTINCT FROM');
    expect(LAST_OWNER_CLAUSE).not.toMatch(/"practiceRole"\s*<>/);
  });

  it('⚠️ the owner count excludes REMOVED members, or a stranded practice looks populated', () => {
    expect(LAST_OWNER_CLAUSE).toMatch(/u2\."deactivatedAt" IS NULL/);
    expect(LAST_OWNER_CLAUSE).toMatch(/u2\."practiceId" = \$2/);
  });

  it('every statement is parameterised, and the placeholders agree across them', () => {
    // ⚠️ A MIS-NUMBERED PLACEHOLDER IS SILENT. `$2` where `$3` was meant does not
    // throw — it binds the wrong value and the guard measures the wrong
    // practice. Both statements take (userId, practiceId, third) in that order
    // precisely so the caller cannot mis-order them, and this pins it.
    for (const sql of [CHANGE_ROLE_GUARDED_SQL, REMOVE_MEMBER_GUARDED_SQL]) {
      expect(sql).toMatch(/id = \$1/);
      expect(sql).toMatch(/"practiceId" = \$2/);
      expect([...sql.matchAll(/\$\d/g)].map((m) => m[0]).every((p) => ['$1', '$2', '$3'].includes(p))).toBe(true);
    }
    expect(PRACTICE_LOCK_SQL).toBe('SELECT id FROM practices WHERE id = $1 FOR UPDATE');
    // No value is ever concatenated into a statement.
    for (const sql of [PRACTICE_LOCK_SQL, CHANGE_ROLE_GUARDED_SQL, PROMOTE_SQL, REMOVE_MEMBER_GUARDED_SQL]) {
      expect(sql).not.toMatch(/\$\{/);
    }
  });
});

describe('⚠️ the lock is taken BEFORE anything the guard trusts', () => {
  it('locks the practice row, then writes — in that order, in one transaction', async () => {
    const calls: string[] = [];
    const tx = {
      $queryRawUnsafe: vi.fn(async (sql: string) => { calls.push(`LOCK:${sql}`); return []; }),
      $executeRawUnsafe: vi.fn(async (sql: string) => { calls.push(`WRITE:${sql.slice(0, 12)}`); return 1; }),
      user: { findFirst: vi.fn(async () => { calls.push('READ'); return { practiceRole: 'OWNER' }; }) },
    };
    vi.doMock('@meddoc/db', () => ({ default: { $transaction: (fn: (t: unknown) => unknown) => fn(tx) } }));
    const { changeRoleGuarded } = await import('../practice-owner-guard');

    const res = await changeRoleGuarded({ practiceId: 'p-1', userId: 'u-2', toRole: 'TECH' });
    expect(res.outcome).toBe('APPLIED');

    // ⚠️ ORDERING IS THE ASSERTION. A read taken before the lock is a snapshot
    // of a set another actor is mid-way through changing, and every downstream
    // guarantee rests on the lock coming first.
    expect(calls[0]).toBe(`LOCK:${PRACTICE_LOCK_SQL}`);
    expect(calls.indexOf('READ')).toBeGreaterThan(0);
    expect(calls.some((c) => c.startsWith('WRITE:'))).toBe(true);
    // and the parameters reach the statement in the pinned order
    expect(tx.$executeRawUnsafe.mock.calls[0].slice(1)).toEqual(['u-2', 'p-1', 'TECH']);
    vi.doUnmock('@meddoc/db');
  });
});
