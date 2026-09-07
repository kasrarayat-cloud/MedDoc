// ============================================================================
// GATE — RULING #210: THE LAST-OWNER INVARIANT HAS EXACTLY ONE DEFINITION
// ----------------------------------------------------------------------------
// ⚠️ WHAT THIS GATE IS FOR, AND WHAT IT DELIBERATELY IS NOT.
//
// It does NOT test that the trigger refuses anything. It CANNOT: the unit job
// declares no `services:` and leaves DATABASE_URL unset, so there is no
// Postgres here to install a trigger into. Behaviour is proven where a real
// database exists — `packages/db/prisma/proofs/admin5-last-owner-trigger-arms.sql`
// (13 arms, each flipping when the trigger is dropped) and
// `...-race.sh` (a 2x2 in which only the no-lock-and-concurrent cell breaks
// the invariant). Pretending to prove behaviour here would be worse than not
// trying, because it would look like coverage.
//
// What it DOES watch is the thing a live-DB proof cannot see: that the rule has
// ONE definition. The predicate exists in two languages — plpgsql in the
// migration, TypeScript in the friendly refusal — and the day someone edits one
// of them, every test in this repository still passes while the two disagree.
// That is this programme's "one rule, many readers" defect, and the cure is a
// gate that READS BOTH and compares, rather than a comment asking politely.
// ============================================================================

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { ACTIVE_OWNER_WHERE } from '../last-owner-invariant';

const REPO = join(__dirname, '..', '..', '..', '..', '..');
const MIGRATION = join(
  REPO, 'packages', 'db', 'prisma', 'migrations',
  '20260907040000_admin5_last_owner_trigger', 'migration.sql'
);
const sql = readFileSync(MIGRATION, 'utf8');

/**
 * The body of `users_is_active_owner`, COMMENTS STRIPPED.
 *
 * ⚠️ The whole-file read would be satisfied by prose. This migration's header
 * names all five columns in a paragraph explaining why the choice matters, so a
 * regex over the file would match the comment and pass with the function empty
 * — canon 114's exact class. Slice to the function, then strip `--` lines.
 */
function activeOwnerSqlBody(): string {
  const start = sql.indexOf('CREATE OR REPLACE FUNCTION users_is_active_owner');
  expect(start, 'users_is_active_owner is not defined in the migration').toBeGreaterThan(-1);
  const end = sql.indexOf('$fn$ LANGUAGE sql IMMUTABLE;', start);
  expect(end, 'users_is_active_owner has no terminator').toBeGreaterThan(start);
  return sql
    .slice(start, end)
    .split('\n')
    .filter((l) => !l.trimStart().startsWith('--'))
    .join('\n');
}

/** Quoted identifiers the SQL predicate actually reads, e.g. `"isActive"`. */
function sqlColumns(): string[] {
  const body = activeOwnerSqlBody();
  const cols = [...body.matchAll(/u\."([A-Za-z]+)"/g)].map((m) => m[1]);
  return [...new Set(cols)].sort();
}

describe('ruling #210 — one definition of an active practice OWNER', () => {
  it('the harness can see the SQL at all (non-vacuity)', () => {
    // Without this, every arm below passes trivially the day the file is moved.
    expect(sql.length).toBeGreaterThan(2000);
    expect(activeOwnerSqlBody()).toContain('PracticeRole');
    expect(sqlColumns().length).toBeGreaterThan(1);
  });

  it('the SQL predicate and the TypeScript predicate name the SAME columns', () => {
    // Both sides DERIVED: the TS side from the exported object's own keys, the
    // SQL side from the function body. Neither is a list retyped in this file,
    // so this arm cannot agree with a stale copy of itself.
    expect(sqlColumns()).toEqual(Object.keys(ACTIVE_OWNER_WHERE).sort());
  });

  it('the predicate is the CONJUNCTION, not `deactivatedAt` alone', () => {
    // The measured reason, kept next to the arm: on production 2026-09-07 six
    // OWNER rows pass `deactivatedAt IS NULL` while unable to sign in, and an
    // eleven-member practice has two such rows and ONE able owner. A predicate
    // that counts an owner who cannot authenticate is a proxy, not the rule.
    for (const column of ['isActive', 'deactivatedAt', 'suspendedAt', 'softDeletedAt'] as const) {
      expect(Object.keys(ACTIVE_OWNER_WHERE)).toContain(column);
    }
    expect(ACTIVE_OWNER_WHERE.practiceRole).toBe('OWNER');
  });

  it('the trigger covers BOTH operations that can remove a seat', () => {
    const trigger = sql.slice(sql.indexOf('CREATE TRIGGER "users_last_owner_guard_before_write"'));
    expect(trigger).toMatch(/BEFORE\s+UPDATE\s+OR\s+DELETE\s+ON\s+"users"/);
    expect(trigger).toContain('FOR EACH ROW');
  });

  it('the guard SERIALIZES before it counts — a count read and then acted on is forbidden', () => {
    const guard = sql.slice(
      sql.indexOf('CREATE OR REPLACE FUNCTION users_last_owner_guard()'),
      sql.indexOf('$fn$ LANGUAGE plpgsql;')
    );
    const lock = guard.indexOf('pg_advisory_xact_lock');
    const count = guard.indexOf('SELECT count(*) INTO owners_left');
    expect(lock, 'the guard takes no lock').toBeGreaterThan(-1);
    // ORDER is the assertion. A lock taken after the count guards nothing, and
    // both would be present either way.
    expect(lock).toBeLessThan(count);
  });

  it('both doors ruling #210 names in scope call the friendly refusal', () => {
    for (const route of ['suspend', 'soft-delete']) {
      const src = readFileSync(
        join(REPO, 'apps', 'transcribe-md', 'src', 'app', 'api', 'admin', 'users', '[id]', route, 'route.ts'),
        'utf8'
      );
      // Not a whole-file `toContain`: assert the call sits BEFORE the write it
      // is supposed to precede, which a comment mentioning it cannot satisfy.
      const call = src.indexOf('await wouldStrandPractice(');
      const write = src.indexOf('.update({');
      expect(call, `${route} does not call wouldStrandPractice`).toBeGreaterThan(-1);
      expect(call, `${route} calls it AFTER the write`).toBeLessThan(write);
    }
  });
});
