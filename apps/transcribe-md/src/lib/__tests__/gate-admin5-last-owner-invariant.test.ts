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

/** A named function's body, COMMENTS STRIPPED — never a whole-file read. */
function fnBody(name: string, terminator: string): string {
  const start = sql.indexOf(`CREATE OR REPLACE FUNCTION ${name}`);
  expect(start, `${name} is not defined in the migration`).toBeGreaterThan(-1);
  const end = sql.indexOf(terminator, start);
  expect(end, `${name} has no terminator`).toBeGreaterThan(start);
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

  it('...and the SAME MEANING — a fully inverted predicate must NOT pass', () => {
    // ⚠️ THIS ARM EXISTS BECAUSE THE ONE ABOVE WAS NOT ENOUGH, AND THE PASS
    // PROVED IT: replacing the predicate with its exact negation — `<> 'OWNER'`,
    // `NOT u."isActive"`, three `IS NOT NULL`, joined by OR — keeps the same
    // five column NAMES and scored 10/10 green. A guard that admits exactly the
    // users it should refuse, with every arm passing. Canon 117's class, in a
    // gate written this session to illustrate canon 121.
    //
    // The cure is to DERIVE the expected SQL from the TypeScript constant and
    // compare CLAUSES, not names. A column list can be satisfied by any
    // arrangement of those columns; a clause set cannot.
    const expected = new Set(
      Object.entries(ACTIVE_OWNER_WHERE).map(([col, val]) => {
        if (val === null) return `u."${col}" IS NULL`;
        if (val === true) return `u."${col}"`;
        return `u."${col}" = '${String(val)}'::"PracticeRole"`;
      })
    );
    const body = activeOwnerSqlBody()
      .replace(/^[\s\S]*?\bSELECT\b/, '')
      .replace(/;\s*$/, '')
      .trim();

    // No disjunction and no negation: their presence alone changes the meaning
    // while leaving every column name in place.
    expect(body, 'the predicate contains OR — it is no longer a conjunction').not.toMatch(/\bOR\b/i);
    expect(body, 'the predicate contains NOT').not.toMatch(/\bNOT\b/i);

    const actual = new Set(body.split(/\bAND\b/i).map((c) => c.replace(/\s+/g, ' ').trim()));
    expect(actual).toEqual(expected);
  });

  it('the LIVE-MEMBER predicate is a conjunction of IS NULL / isActive too', () => {
    const body = fnBody('users_is_live_member', '$fn$ LANGUAGE sql IMMUTABLE;')
      .replace(/^[\s\S]*?\bSELECT\b/, '')
      .replace(/;\s*$/, '')
      .trim();
    expect(body).not.toMatch(/\bOR\b/i);
    expect(body).not.toMatch(/\bNOT\b/i);
    expect(new Set(body.split(/\bAND\b/i).map((c) => c.replace(/\s+/g, ' ').trim()))).toEqual(
      new Set([
        'u."isActive"',
        'u."deactivatedAt" IS NULL',
        'u."softDeletedAt" IS NULL',
        'u."suspendedAt" IS NULL',
      ])
    );
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
    const i = sql.indexOf('CREATE CONSTRAINT TRIGGER "users_last_owner_guard_after_write"');
    expect(i, 'the constraint trigger is not created').toBeGreaterThan(-1);
    const trigger = sql.slice(i);
    expect(trigger).toMatch(/AFTER\s+UPDATE\s+OR\s+DELETE\s+ON\s+"users"/);
    expect(trigger).toContain('FOR EACH ROW');
  });

  it('it is a CONSTRAINT trigger deferred to the END of the statement — not a BEFORE row trigger', () => {
    // ⚠️ THIS ARM EXISTS BECAUSE THE BEFORE FORM WAS BUILT FIRST AND WAS WRONG.
    // A BEFORE row trigger judges each row before the statement's OTHER rows are
    // applied, so tearing a whole practice down in one DELETE — which is exactly
    // what the E2E suite's own cleanup does (tests/e2e/helpers/cleanup.ts:99) —
    // is refused, because the members being deleted alongside the owner still
    // look like survivors. Worse, it is ORDER-DEPENDENT: whether the owner's row
    // is reached first decides whether a legitimate teardown succeeds.
    //
    // The invariant is a property of the statement's RESULT, so the check has to
    // run once the statement has produced it. Reverting to `BEFORE ... FOR EACH
    // ROW` would re-break the E2E teardown intermittently, and nothing else here
    // would notice — so this arm names the shape rather than the behaviour.
    const i = sql.indexOf('CREATE CONSTRAINT TRIGGER');
    const trigger = sql.slice(i, sql.indexOf(';', i));
    expect(trigger).toContain('DEFERRABLE INITIALLY IMMEDIATE');

    // and no BEFORE row trigger on users survives anywhere in the migration
    const code = sql
      .split('\n')
      .filter((l) => !l.trimStart().startsWith('--'))
      .join('\n');
    expect(code).not.toMatch(/BEFORE\s+(INSERT\s+OR\s+)?UPDATE(\s+OR\s+DELETE)?\s+ON\s+"users"/);
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

  it('there is a LIVE-MEMBER definition too, and it excludes suspension', () => {
    // ⚠️ BOTH HALVES WERE DEFECTS FOUND BY THE ADVERSARIAL PASS.
    // Counting a SOFT-DELETED ex-employee as a member made a solo owner's own
    // account deletion permanently impossible, and the refusal named a remedy
    // ("transfer ownership") that a soft-deleted row cannot receive. Counting a
    // SUSPENDED person as a member would block suspending a solo practice
    // owner, which is a legitimate operations action.
    const body = fnBody('users_is_live_member', '$fn$ LANGUAGE sql IMMUTABLE;');
    for (const col of ['isActive', 'deactivatedAt', 'softDeletedAt', 'suspendedAt']) {
      expect(body, `users_is_live_member ignores ${col}`).toContain(col);
    }
  });

  it('exemption 2 counts the row ITSELF when the write leaves it behind', () => {
    // On a DELETE the row is going, so only other members can be stranded. On an
    // UPDATE the row STAYS — and a solo owner demoting themselves is the person
    // stranded. The first version counted only other rows and allowed it; 2 of 5
    // race runs ended in exactly that state.
    const guard = fnBody('users_last_owner_guard()', '$fn$ LANGUAGE plpgsql;');
    const count = guard.indexOf('INTO members_left');
    const self = guard.indexOf('members_left := members_left + 1');
    expect(self, 'nothing adds the surviving row to the member count').toBeGreaterThan(-1);
    expect(self, 'the self-count runs before the count it adjusts').toBeGreaterThan(count);
    expect(guard.slice(count, self)).toMatch(/TG_OP\s*=\s*'UPDATE'|users_is_live_member\(NEW\)/);
  });

  it('the orphan arm fires on INSERT **and** UPDATE — an unsuspend adds a member too', () => {
    // An INSERT is not the only way to put a live member into an ownerless
    // practice: unsuspending or reactivating one does it as an UPDATE whose OLD
    // row is not an active owner, which the removal guard returns early on.
    const i = sql.indexOf('CREATE CONSTRAINT TRIGGER "users_no_orphan_member_after_insert"');
    expect(i, 'the orphan-member trigger is not created').toBeGreaterThan(-1);
    expect(sql.slice(i, sql.indexOf(';', i))).toMatch(/AFTER\s+INSERT\s+OR\s+UPDATE\s+ON\s+"users"/);
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
