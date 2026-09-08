// ============================================================================
// GATE — RULING #210: THE LAST-OWNER INVARIANT HAS EXACTLY ONE DEFINITION
// ----------------------------------------------------------------------------
// ⚠️ WHAT THIS GATE IS FOR, AND WHAT IT DELIBERATELY IS NOT.
//
// It does NOT test that the trigger refuses anything. It CANNOT: the unit job
// declares no `services:` and leaves DATABASE_URL unset, so there is no
// Postgres here to install a trigger into. Behaviour is proven where a real
// database exists — `packages/db/prisma/proofs/admin5-last-owner-trigger-arms.sql`
// (23 arms, each flipping when the trigger is dropped) and
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

import { beforeEach, describe, expect, it, vi } from 'vitest';

// ⚠️ THE MOCK EXISTS BECAUSE EVERY ARM IN THIS FILE READ SOURCE AND NONE DROVE
// THE FUNCTION — round two measured it: `wouldStrandPractice` reduced to
// `return { wouldStrand: false }` kept all fourteen arms GREEN. A gate that can
// only read the guard cannot tell you the guard still runs.
const userFindUnique = vi.fn();
const userCount = vi.fn();
vi.mock('@meddoc/db', () => ({
  default: {
    user: {
      findUnique: (...a: unknown[]) => userFindUnique(...a),
      count: (...a: unknown[]) => userCount(...a),
    },
  },
}));

import {
  ACTIVE_OWNER_WHERE,
  IsolationLevelUnsupportedError,
  LIVE_MEMBER_WHERE,
  PRACTICE_LOCK_KEY,
  activeOwnerSql,
  liveMemberSql,
  withPracticeLock,
  wouldStrandPractice,
} from '../last-owner-invariant';

const REPO = join(__dirname, '..', '..', '..', '..', '..');
// The app's own `src`, for the door-order arms (#268) and the Serializable
// audit (#269). Derived from __dirname so it is right in a worktree too.
const SRC = join(__dirname, '..', '..');
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
  return stripSqlComments(sql.slice(start, end));
}

/** A named function's body, COMMENTS STRIPPED — never a whole-file read. */
function fnBody(name: string, terminator: string): string {
  const start = sql.indexOf(`CREATE OR REPLACE FUNCTION ${name}`);
  expect(start, `${name} is not defined in the migration`).toBeGreaterThan(-1);
  const end = sql.indexOf(terminator, start);
  expect(end, `${name} has no terminator`).toBeGreaterThan(start);
  return stripSqlComments(sql.slice(start, end));
}

/** One SQL statement, from its opening keyword to its `;`, COMMENTS STRIPPED. */
function statement(opening: string): string {
  const start = sql.indexOf(opening);
  expect(start, `${opening} is not in the migration`).toBeGreaterThan(-1);
  const end = sql.indexOf(';', start);
  expect(end, `${opening} has no terminator`).toBeGreaterThan(start);
  return sql
    .slice(start, end)
    .split('\n')
    .map(stripComment)
    .join('\n');
}

/**
 * Remove a `--` comment from a line — TRAILING as well as whole-line.
 *
 * ⚠️ THE FIRST VERSION DROPPED ONLY LINES THAT *START* WITH `--`, and the
 * adversarial pass found the gap: a column deleted from the predicate and left
 * in a TRAILING comment on a live line survived the strip, so the column-name
 * arm still saw it. The clause-set arm catches that case, but a defence that
 * relies on its sibling is one edit from being no defence.
 */
function stripComment(line: string): string {
  const i = line.indexOf('--');
  return i === -1 ? line : line.slice(0, i);
}

/**
 * ⚠️ BLOCK COMMENTS TOO — RULING #240c.
 *
 * `stripComment` removes `--` to end-of-line and nothing else, so a SQL BLOCK
 * comment (slash-star … star-slash) survived every "is it in the CODE" arm. Measured in round two: the
 * advisory lock — the one #220 ratified *because it was proven load-bearing* —
 * could be DELETED and replaced by a block comment naming it, with the gate
 * 14/14 and all arms green.
 *
 * ⚠️ THIS IS THE SECOND TIME THE SAME ARM HAS BEEN DEFEATED BY A COMMENT. The
 * arm's own header records the first: *"Reading the raw slice let the lock be
 * DELETED and replaced by a comment mentioning it — measured 12/12 green."* The
 * fix then was to strip comments; it stripped one of the two kinds SQL has.
 * **Closing an instance is not closing the class**, and the second instance
 * arrived in the same arm.
 */
function stripSqlComments(text: string): string {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .split('\n')
    .map(stripComment)
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

  it('ruling #221 — the SQL GENERATOR emits exactly the migration\'s predicate', () => {
    // This is what makes "one constant, three readers" real rather than stated.
    // #1026 writes raw SQL; without a generator its only options were to restate
    // the rule or to widen its subquery by hand — the second copy #221 forbids.
    // Compared as CLAUSE SETS, so whitespace and ordering are free and MEANING
    // is not: an inverted or widened generator cannot pass this.
    const generated = new Set(
      activeOwnerSql('u').split(/\bAND\b/i).map((c) => c.replace(/\s+/g, ' ').trim())
    );
    const migration = new Set(
      activeOwnerSqlBody()
        .replace(/^[\s\S]*?\bSELECT\b/, '')
        .replace(/;\s*$/, '')
        .split(/\bAND\b/i)
        .map((c) => c.replace(/\s+/g, ' ').trim())
    );
    expect(generated).toEqual(migration);
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
    // Sliced to the statement's own terminator and comment-stripped: the raw
    // slice ran to end-of-file, so any later comment naming the operations
    // satisfied it.
    const trigger = statement('CREATE CONSTRAINT TRIGGER "users_last_owner_guard_after_write"');
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
    expect(statement('CREATE CONSTRAINT TRIGGER "users_last_owner_guard_after_write"'))
      .toContain('DEFERRABLE INITIALLY IMMEDIATE');

    // and no BEFORE row trigger on users survives anywhere in the migration
    const code = sql.split('\n').map(stripComment).join('\n');
    expect(code).not.toMatch(/BEFORE\s+(INSERT\s+OR\s+)?UPDATE(\s+OR\s+DELETE)?\s+ON\s+"users"/);
  });

  it('the guard SERIALIZES before it counts — ORDERING ONLY; the AUTHORITY is pg_locks', () => {
    // ⚠️ THIS ARM IS DEMOTED — RULING #251. IT IS NOT THE PROOF THAT THE LOCK
    // EXISTS, AND IT MUST NEVER AGAIN BE CITED AS ONE.
    //
    // It has been defeated by a comment TWICE. First by a `--` line, which was
    // fixed by stripping `--`. Then, in the very next round, by a NESTED block
    // comment — SQL block comments nest and a non-greedy stripper stops at the
    // first terminator — with the gate 23/23 and all SQL arms green while the
    // running function held NO LOCK AT ALL.
    //
    // ⚠️ THE SECOND FIX WAS WRITTEN BY SOMEBODY WHO HAD JUST READ THE FIRST.
    // That is the argument for #251: the defect is not any particular regex, it
    // is asking a question about TEXT when the claim is about BEHAVIOUR.
    //
    // THE AUTHORITY IS NOW `LOCK-CONTROL (pg_locks)` in
    // `admin5-last-owner-trigger-arms.sql`: it takes a write that reaches the
    // counting path and asks the SERVER whether the lock is held, keyed on the
    // exact pair the guard computes, with a BEFORE reading so the AFTER means
    // something. A commented-out lock holds no lock and it reads 0|0.
    //
    // What survives here is the one thing pg_locks cannot see: the ORDER of the
    // statements in the source. A lock taken after the count guards nothing, and
    // both would be present either way — so this stays, as a cheap secondary.
    const guard = fnBody('users_last_owner_guard()', '$fn$ LANGUAGE plpgsql;');
    const lock = guard.indexOf('pg_advisory_xact_lock');
    const count = guard.indexOf('SELECT count(*) INTO owners_left');
    const forUpdate = guard.indexOf('FOR UPDATE');
    // ⚠️ NOT EVIDENCE THE LOCK EXISTS — see the header. `LOCK-CONTROL (pg_locks)`
    // is what proves that; this only pins the ORDER of what is written.
    expect(lock, 'the guard names no advisory lock in its source ORDER').toBeGreaterThan(-1);
    expect(forUpdate, 'the guard takes no row lock — REPEATABLE READ would skew').toBeGreaterThan(-1);
    // ORDER is the assertion. A lock taken after the count guards nothing, and
    // both would be present either way.
    expect(lock).toBeLessThan(count);
    expect(forUpdate).toBeLessThan(count);
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
    expect(statement('CREATE CONSTRAINT TRIGGER "users_no_orphan_member_after_insert"'))
      .toMatch(/AFTER\s+INSERT\s+OR\s+UPDATE\s+ON\s+"users"/);
  });

  it('the friendly refusal SELECTS every column its predicate reads', () => {
    // ⚠️ A FORGOTTEN COLUMN HERE IS SILENT, WHICH IS WHY IT IS AN ARM.
    // Prisma returns only what is selected; a missing field arrives `undefined`,
    // `undefined === null` is false, and the row quietly stops counting as an
    // active owner. No error, no red test, and the friendly refusal starts
    // disagreeing with the trigger. The source must DERIVE the select from
    // ACTIVE_OWNER_WHERE rather than restate it.
    const src = readFileSync(join(__dirname, '..', 'last-owner-invariant.ts'), 'utf8');
    const call = src.slice(src.indexOf('prisma.user.findUnique'), src.indexOf('const isActiveOwner'));
    expect(call).toContain('Object.keys(ACTIVE_OWNER_WHERE)');
    // and no hand-written restatement of a predicate column in that select
    for (const col of Object.keys(ACTIVE_OWNER_WHERE)) {
      expect(call, `${col} is restated by hand in the select`).not.toContain(`${col}: true`);
    }
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

  // ══════════════════════════════════════════════════════════════════════════
  // RULING #239 — "LIVE MEMBER" GETS ONE PREDICATE, AS "ABLE OWNER" DID.
  // ══════════════════════════════════════════════════════════════════════════
  it('ruling #239 — `liveMemberSql` emits exactly the migration\'s live-member predicate', () => {
    // Same normalisation the #221 arm uses: drop everything up to SELECT and the
    // trailing `;`, then compare as CLAUSE SETS so whitespace and ordering are
    // free and MEANING is not.
    const body = fnBody('users_is_live_member', '$fn$ LANGUAGE sql IMMUTABLE;')
      .replace(/^[\s\S]*?\bSELECT\b/, '')
      .replace(/;\s*$/, '');
    const generated = new Set(
      liveMemberSql('u').split(/\bAND\b/i).map((c) => c.replace(/\s+/g, ' ').trim()),
    );
    const migration = new Set(
      body.split(/\bAND\b/i).map((c) => c.replace(/\s+/g, ' ').trim()),
    );
    expect(generated, 'the generator and the migration disagree clause-for-clause').toEqual(migration);
    expect(generated.size, 'the live-member predicate collapsed to nothing').toBe(4);
  });

  it('ruling #239 — the TS filter names the same columns as the SQL', () => {
    const cols = new Set(
      [...fnBody('users_is_live_member', '$fn$ LANGUAGE sql IMMUTABLE;')
        .replace(/^[\s\S]*?\bSELECT\b/, '')
        .matchAll(/u\."([A-Za-z]+)"/g)].map((m) => m[1]!),
    );
    expect(new Set(Object.keys(LIVE_MEMBER_WHERE))).toEqual(cols);
  });
});

// ============================================================================
// ⚠️ BEHAVIOURAL COVERAGE — ROUND TWO FOUND THIS FILE HAD NONE.
//
// Every arm above reads SOURCE. That is the right instrument for "the two
// copies of a predicate agree", and it is the wrong instrument for "the guard
// still runs": `wouldStrandPractice` reduced to `return { wouldStrand: false }`
// kept 14 of 14 green. These arms DRIVE it.
// ============================================================================
describe('ruling #239 — the friendly refusal counts LIVE members, not rows', () => {
  const OWNER = {
    id: 'u1',
    practiceId: 'p1',
    practiceRole: 'OWNER',
    isActive: true,
    deactivatedAt: null,
    suspendedAt: null,
    softDeletedAt: null,
  };

  beforeEach(() => {
    userFindUnique.mockReset();
    userCount.mockReset();
    userFindUnique.mockResolvedValue(OWNER);
  });

  /** `count` is called twice: [0] able owners left, [1] live members left. */
  const counts = (ownersLeft: number, membersLeft: number) => {
    userCount.mockResolvedValueOnce(ownersLeft).mockResolvedValueOnce(membersLeft);
  };

  it('⚠️ NON-VACUITY — the last able owner WITH a live member DOES strand', async () => {
    counts(0, 1);
    const v = await wouldStrandPractice('u1');
    expect(v.wouldStrand, 'the guard no longer refuses anything — every arm below is vacuous').toBe(true);
  });

  it('exemption 1 — not an active owner, so nothing is lost', async () => {
    userFindUnique.mockResolvedValue({ ...OWNER, practiceRole: 'CLINICIAN' });
    expect((await wouldStrandPractice('u1')).wouldStrand).toBe(false);
    expect(userCount, 'it counted before deciding the row was exempt').not.toHaveBeenCalled();
  });

  it('another able owner remains — nothing is lost', async () => {
    counts(1, 5);
    expect((await wouldStrandPractice('u1')).wouldStrand).toBe(false);
  });

  it('exemption 2 — nobody left to strand', async () => {
    counts(0, 0);
    expect((await wouldStrandPractice('u1')).wouldStrand).toBe(false);
  });

  it('⚠️ THE MEMBER COUNT IS FILTERED BY `LIVE_MEMBER_WHERE` — kills the bare row count', async () => {
    counts(0, 0);
    await wouldStrandPractice('u1');
    const memberQuery = userCount.mock.calls[1][0] as { where: Record<string, unknown> };
    for (const [column, value] of Object.entries(LIVE_MEMBER_WHERE)) {
      expect(
        memberQuery.where[column],
        `the member count does not filter on ${column} — it counts rows the ` +
          `trigger does not count, so this file refuses a write the database allows`,
      ).toBe(value);
    }
  });

  it('⚠️ …AND THE OWNER COUNT IS FILTERED BY `ACTIVE_OWNER_WHERE`', async () => {
    counts(0, 0);
    await wouldStrandPractice('u1');
    const ownerQuery = userCount.mock.calls[0][0] as { where: Record<string, unknown> };
    for (const [column, value] of Object.entries(ACTIVE_OWNER_WHERE)) {
      expect(ownerQuery.where[column], `the owner count does not filter on ${column}`).toBe(value);
    }
  });

  it('⚠️ BOTH COUNTS EXCLUDE THE ROW BEING WRITTEN', async () => {
    counts(0, 0);
    await wouldStrandPractice('u1');
    for (const call of userCount.mock.calls) {
      expect((call[0] as { where: { id?: unknown } }).where.id).toEqual({ not: 'u1' });
    }
  });
});

// ============================================================================
// RULINGS #268 / #269 — THE LOCK IS TAKEN BEFORE THE WRITE, AND THE LEVEL IS
// ASSERTED.
// ----------------------------------------------------------------------------
// ⚠️ WHAT MAKES THESE ARMS NECESSARY: the deadlock they close is INVISIBLE to
// every other arm in this file. It needs two concurrent connections, so a
// single-threaded unit suite cannot reach it — the shipped code passed 23 of 23
// here while deadlocking 10 times out of 10 against a real Postgres.
//
// So these arms do NOT try to reproduce the race. They assert the two
// STRUCTURAL properties the race proof depends on, which a unit suite CAN see:
// that the lock is taken BEFORE the write at every door, and that the helper
// refuses a level it cannot be correct at. The race itself is proved in
// `prisma/proofs/`, and the numbers live in the §2.5 rows file.
// ============================================================================
describe('#268 — the practice lock is taken BEFORE any user-row write', () => {
  const DOORS: ReadonlyArray<readonly [string, string]> = [
    ['the role-change door', join(SRC, 'actions', 'practice-members.ts')],
    ['the admin suspend route', join(SRC, 'app', 'api', 'admin', 'users', '[id]', 'suspend', 'route.ts')],
    ['the admin soft-delete route', join(SRC, 'app', 'api', 'admin', 'users', '[id]', 'soft-delete', 'route.ts')],
    ['the self-service delete door', join(SRC, 'app', 'api', 'settings', 'delete-account', 'route.ts')],
  ];

  it.each(DOORS)('%s calls withPracticeLock', (_name, file) => {
    const src = readFileSync(file, 'utf8');
    expect(src, `${file} does not import withPracticeLock`).toContain('withPracticeLock');
  });

  it.each(DOORS)('%s takes the lock BEFORE its write, not after', (_name, file) => {
    const src = readFileSync(file, 'utf8');
    const lockAt = src.indexOf('withPracticeLock(');
    expect(lockAt, 'no withPracticeLock call').toBeGreaterThan(-1);

    // ⚠️ ORDER IS THE ENTIRE POINT — A LOCK TAKEN AFTER THE ROW WRITE ORDERS
    // NOTHING, and it is the shape that deadlocked. Measured on this branch:
    // lock-after 10/10 deadlocks, lock-before 0/10.
    // The write is found by the FIRST user-row mutation in the file.
    const writeAt = [
      /\btx\.user\.(?:update|updateMany|delete|deleteMany|create)\b/,
      /\(tx\.user as any\)\.update\b/,
      /\bprisma\.user\.(?:update|updateMany|delete|deleteMany)\b/,
    ]
      .map((re) => src.search(re))
      .filter((i) => i > -1)
      .sort((a, b) => a - b)[0];

    // POSITIVE CONTROL: a door with no user-row write at all would pass
    // vacuously, and three of these four would have.
    expect(writeAt, `${file} has no user-row write — this arm would be vacuous`).toBeGreaterThan(-1);
    expect(
      lockAt,
      `${file} writes a user row at ${writeAt} before taking the lock at ${lockAt} — ` +
        'that is the shape that deadlocked 10 of 10',
    ).toBeLessThan(writeAt as number);
  });

  it('⚠️ the helper uses the TRIGGER\'s key, and does not re-implement hashtext', () => {
    const src = readFileSync(join(SRC, 'lib', 'last-owner-invariant.ts'), 'utf8');
    // The same literal the migration passes to hashtext. A second key would
    // take a DIFFERENT lock while looking identical.
    expect(PRACTICE_LOCK_KEY).toBe('users_last_owner_guard');
    expect(sql, 'the migration no longer locks on this key').toContain(
      `hashtext('${PRACTICE_LOCK_KEY}')`,
    );
    expect(src, 'the helper computes its own hash instead of using hashtext').toContain(
      'hashtext(${PRACTICE_LOCK_KEY})',
    );
  });

  it('⚠️ the TRIGGER KEEPS its own lock — the helper does not replace it', () => {
    // A helper is application code and the next writer will not call it. If
    // this arm reds because the trigger's lock was removed "now that the
    // application takes it", that is the defect, not the test.
    // ⚠️ THE CALL FORM, NOT THE BARE NAME — AND THIS ARM CAUGHT ITSELF.
    // Its first version counted /pg_advisory_xact_lock/, which is a SUBSTRING
    // of any renaming: a mutation that replaced every call with
    // `pg_advisory_xact_lock_REMOVED_BY_MUTATION` left all three matches
    // standing and the arm passed 38 of 38 with the trigger's lock gone.
    // Matching the open paren means the identifier has to END there.
    const calls = (sql.match(/pg_advisory_xact_lock\s*\(/g) ?? []).length;
    expect(calls, 'the trigger stopped taking its own advisory lock').toBeGreaterThanOrEqual(2);
  });
});

describe('#269 — the guard refuses above READ COMMITTED', () => {
  // ⚠️ THE DOUBLE CARRIES **BOTH** METHODS, AND ITS FIRST VERSION DID NOT —
  // WHICH IS WHY THESE ARMS COULD NOT SEE A 500. The helper took its lock with
  // `$queryRaw`, the double only had `$queryRaw`, so every arm here passed
  // while the real route threw: `pg_advisory_xact_lock` returns `void` and
  // `$queryRaw` cannot deserialize a void column. The e2e caught it on the
  // ordinary suspend of a solo owner.
  //
  // A test double that offers FEWER methods than the client cannot witness the
  // wrong one being chosen. Both are here now, and the arm below pins which one
  // the lock uses.
  const txAt = (level: string) => ({
    $queryRaw: vi.fn(async () => [{ level }]) as unknown as <R>(
      q: TemplateStringsArray,
      ...v: unknown[]
    ) => Promise<R>,
    $executeRaw: vi.fn(async () => 1) as unknown as (
      q: TemplateStringsArray,
      ...v: unknown[]
    ) => Promise<number>,
  });

  it('READ COMMITTED is accepted, and the lock is actually taken', async () => {
    const tx = txAt('read committed');
    const write = vi.fn(async () => 'wrote');
    await expect(withPracticeLock(tx, 'prac-1', write)).resolves.toBe('wrote');
    // ⚠️ NOT JUST "IT RESOLVED" — the lock query must have run. A helper that
    // checked the level and forgot the lock would satisfy a bare resolve.
    // ⚠️ THE LOCK IS AN **EXECUTE**, NOT A QUERY, AND THE DISTINCTION IS THE
    // DIFFERENCE BETWEEN A WORKING ROUTE AND A 500. `pg_advisory_xact_lock`
    // returns `void` (asserted from `pg_get_function_result`, not assumed) and
    // `$queryRaw` must deserialize the row it gets back — it cannot deserialize
    // a void column. `billing-charge.ts:453` already took its advisory lock the
    // right way one package over.
    const probes = (tx.$queryRaw as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    const locks = (tx.$executeRaw as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    expect(probes.length, 'the isolation probe was not a query').toBe(1);
    expect(locks.length, 'the lock was never issued, or was issued as a QUERY').toBe(1);
    expect(String(locks[0][0]), 'the executed statement is not the advisory lock').toContain(
      'pg_advisory_xact_lock',
    );
    expect(write).toHaveBeenCalledTimes(1);
  });

  it.each(['repeatable read', 'serializable'])(
    '⚠️ %s is REFUSED — and refused BEFORE the write runs',
    async (level) => {
      const tx = txAt(level);
      const write = vi.fn(async () => 'wrote');
      await expect(withPracticeLock(tx, 'prac-1', write)).rejects.toBeInstanceOf(
        IsolationLevelUnsupportedError,
      );
      // ⚠️ THE ORDER IS THE SAFETY PROPERTY. Refusing after the write would
      // leave the forbidden state committed and then complain about it.
      expect(write, 'the write ran before the refusal').not.toHaveBeenCalled();
      // and the lock was never taken either — one query, the level probe.
      expect(
        (tx.$queryRaw as unknown as { mock: { calls: unknown[][] } }).mock.calls.length,
        'more than the level probe ran inside a level that cannot be correct',
      ).toBe(1);
      expect(
        (tx.$executeRaw as unknown as { mock: { calls: unknown[][] } }).mock.calls.length,
        'the lock was taken inside a level that cannot be correct',
      ).toBe(0);
    },
  );

  it('⚠️ the refusal NAMES the level it saw — a bare "unsupported" is unactionable', () => {
    expect(new IsolationLevelUnsupportedError('serializable').message).toContain('serializable');
  });

  it('⚠️ NO Serializable transaction writes a user row — the audit #269 requires', () => {
    // ⚠️ THIS AUDIT PRECEDES THE REFUSAL, AND THE ORDER IS THE RULING'S. If a
    // shipped Serializable transaction legitimately wrote a user row, the
    // refusal above would convert this guard into an outage. Measured: none do.
    const files = [
      join(SRC, 'lib', 'template-twin', 'fill-engine.ts'),
      join(SRC, 'lib', 'template-twin', 'certification-lifecycle.ts'),
      join(SRC, 'lib', 'template-twin', 'synthetic-test.ts'),
      join(SRC, 'app', 'api', 'visits', '[id]', 'sign', 'route.ts'),
    ];
    const WRITE = /\btx\.user\.(?:update|updateMany|delete|deleteMany|create)\b|\(tx\.user as any\)\.update\b/;

    // POSITIVE CONTROL FIRST, from a DIFFERENT era than the subject: the same
    // pattern must FIND the writes that do exist, or an empty result below
    // means only that the regex is broken.
    const control = join(SRC, 'app', 'api', 'settings', 'change-password', 'route.ts');
    expect(
      WRITE.test(readFileSync(control, 'utf8')),
      'the user-write pattern no longer matches a known user write — the audit below is void',
    ).toBe(true);

    for (const f of files) {
      const src = readFileSync(f, 'utf8');
      if (!src.includes('isolationLevel')) continue;
      expect(
        WRITE.test(src),
        `${f} runs Serializable AND writes a user row — #269's refusal would make it a 500`,
      ).toBe(false);
    }
  });
});
