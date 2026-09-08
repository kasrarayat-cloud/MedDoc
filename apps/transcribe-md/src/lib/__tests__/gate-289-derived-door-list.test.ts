// ============================================================================
// RULING #289 — THE DOOR LIST IS **DERIVED**, NOT ENUMERATED.
// ----------------------------------------------------------------------------
// The #268 arms carried a hand-written list of four doors. The migration's own
// header had already said why that cannot hold:
//
//     "That is five doors today and the set is OPEN: the sixth is written by
//      whoever adds the next admin surface, and they will not read this file.
//      A guard per door is a guard per door you remembered."
//
// ⚠️ AND THE SIXTH ALREADY EXISTED — FOUR OF THEM. `unsuspend`, `force-logout`,
// `grant-admin` and `revoke-admin` all write a `users` row and none was in the
// list. They were invisible to the #268 arms twice over: not enumerated, and
// written as `(prisma.user as any).update(...)`, a shape the arms' own write
// regex did not match. **A cast hides a write from the compiler and from the
// scanner at the same time** — the same escape hatch that let four call sites
// survive #287's rename while `tsc` returned 0.
//
// So the universe is READ FROM THE FILESYSTEM and every writer must be
// classified. An unclassified writer REDS, by name.
//
// ⚠️ AND THE EXEMPTIONS ARE CHECKED, NOT ASSERTED. "This column is not in the
// trigger's predicate" is a claim about `migration.sql`, so the predicate is
// PARSED FROM THAT FILE and the exempt writers' own `data: {}` keys are
// measured against it. A prose exemption rots the day somebody adds
// `suspendedAt` to a profile update; this one reds.
// ============================================================================
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const APP = join(__dirname, '..', '..', '..');
const MIGRATION = join(
  APP, '..', '..', 'packages', 'db', 'prisma', 'migrations',
  '20260907040000_admin5_last_owner_trigger', 'migration.sql',
);

/** Every write shape that reaches a `users` row — INCLUDING the `as any` cast. */
const USER_WRITE =
  /(?:\(\s*)?(?:prisma|tx|client|db)\s*\.\s*user\s*(?:as\s+\w+\s*\)\s*)?\.\s*(?:update|updateMany|create|createMany|delete|deleteMany|upsert)\b/;

const stripComments = (s: string) =>
  s
    .split('\n')
    .filter((l) => !l.trimStart().startsWith('//') && !l.trimStart().startsWith('*'))
    .join('\n');

function sourceFiles(): string[] {
  return execFileSync('git', ['ls-files', 'src'], { cwd: APP, encoding: 'utf8' })
    .split('\n')
    .filter((f) => f.endsWith('.ts') && !f.includes('__tests__') && !f.endsWith('.test.ts'));
}

/** Files that write a `users` row, derived — never listed. */
function writers(): { file: string; src: string; locked: boolean }[] {
  return sourceFiles()
    .map((file) => ({ file, src: stripComments(readFileSync(join(APP, file), 'utf8')) }))
    .filter((f) => USER_WRITE.test(f.src))
    .map((f) => ({ ...f, locked: f.src.includes('withPracticeLock') }));
}

/**
 * The columns the two trigger predicates read, PARSED FROM THE MIGRATION.
 * `practiceId` joins them because exemption 2 compares `NEW."practiceId"` with
 * `OLD."practiceId"` — moving an owner to another practice removes a seat from
 * the old one just as surely as demoting them.
 */
function watchedColumns(): Set<string> {
  const sql = readFileSync(MIGRATION, 'utf8');
  const cols = new Set<string>(['practiceId']);
  for (const fn of ['users_is_active_owner', 'users_is_live_member']) {
    const start = sql.indexOf(`CREATE OR REPLACE FUNCTION ${fn}(`);
    expect(start, `${fn} is not in the migration — the parser is reading the wrong file`)
      .toBeGreaterThan(-1);
    const body = sql.slice(start, sql.indexOf('$fn$ LANGUAGE', start));
    for (const m of body.matchAll(/u\."(\w+)"/g)) cols.add(m[1]!);
  }
  return cols;
}

/** The `data: { … }` keys of every user-row write in a file. */
function writtenColumns(src: string): string[] {
  const keys: string[] = [];
  for (let i = src.search(USER_WRITE); i > -1; ) {
    const d = src.indexOf('data:', i);
    if (d < 0) break;
    const open = src.indexOf('{', d);
    let depth = 0;
    let end = open;
    for (; end < src.length; end += 1) {
      if (src[end] === '{') depth += 1;
      else if (src[end] === '}' && (depth -= 1) === 0) break;
    }
    for (const m of src.slice(open, end).matchAll(/(?:^|[{,\s])(\w+)\s*:/g)) keys.push(m[1]!);
    const rest = src.slice(end);
    const next = rest.search(USER_WRITE);
    if (next < 0) break;
    i = end + next;
  }
  return keys;
}

// ⚠️ EVERY EXEMPTION CARRIES ITS REASON, AND NINE OF THE TEN ARE MACHINE-CHECKED
// by the column arm below. Only `actions/auth.ts` is exempt on an argument a
// column list cannot express, so it is the one written out at length.
const EXEMPT: Record<string, string> = {
  'src/actions/profile.ts': 'writes name/specialty/npi/clinicName — no predicate column',
  'src/app/api/auth/confirm-email/route.ts': 'writes email — no predicate column',
  'src/app/api/auth/verify-email/route.ts': 'writes emailVerified — no predicate column',
  'src/app/api/auth/reset-password/route.ts': 'writes failedLoginCount/lockedUntil — no predicate column',
  'src/app/api/settings/change-password/route.ts': 'writes passwordHash/failedLoginCount/lockedUntil — no predicate column',
  'src/app/api/mfa/disable/route.ts': 'writes mfa* — no predicate column',
  'src/app/api/mfa/enroll/route.ts': 'writes mfa* — no predicate column',
  'src/app/api/mfa/verify-enrollment/route.ts': 'writes mfa* — no predicate column',
  'src/lib/nextauth.ts': 'writes failedLoginCount/lastLogin — no predicate column',
  // ⚠️ THE ONE EXEMPT ON ORDER RATHER THAN ON COLUMNS, and it is the door the
  // derivation FOUND. An INVITED signup inserts a live non-owner into an
  // EXISTING practice: `users_no_orphan_member` fails exemption 1 (not an active
  // owner) and cannot use exemption 2 (that arm is `TG_OP = 'UPDATE'`), so the
  // trigger DOES take `pg_advisory_xact_lock`. It is safe anyway because it takes
  // it FIRST — the statement before it on that path is `tx.practice.findUnique`,
  // a plain read with no `FOR UPDATE` — which is the same acquisition order
  // `withPracticeLock` establishes, so the two cannot deadlock against each
  // other. The SOLO path never reaches the lock at all: it mints its practice and
  // creates the row as OWNER, so exemption 1 returns.
  'src/actions/auth.ts': 'INSERT is the first row lock in its transaction — same order withPracticeLock establishes',
};

describe('#289 — the door universe is derived from the filesystem', () => {
  const WRITERS = writers();

  it('POSITIVE CONTROL — the scan finds writers, across more than one directory', () => {
    expect(WRITERS.length, 'the scan matched nothing — the matcher is broken').toBeGreaterThan(10);
    expect(new Set(WRITERS.map((w) => w.file.split('/').slice(0, 3).join('/'))).size)
      .toBeGreaterThan(2);
  });

  it('⚠️ THE DETECTOR SEES THE CAST — the shape that hid four doors', () => {
    // Not a hypothetical: all four unlisted doors were written this way, and the
    // #268 arms' regex matched `(tx.user as any).update` but not
    // `(prisma.user as any).update`.
    for (const shape of [
      'await (prisma.user as any).update({',
      'await (tx.user as any).update({',
      'await prisma.user.update({',
      'await tx.user.updateMany({',
      'const u = await tx.user.create({',
    ]) {
      expect(USER_WRITE.test(shape), `the detector is blind to \`${shape}\``).toBe(true);
    }
    // NEGATIVE CONTROL: it must not match a read, or every reader becomes a door
    // and the classification is noise.
    for (const shape of ['await prisma.user.findUnique({', 'await tx.userSession.deleteMany({']) {
      expect(USER_WRITE.test(shape), `the detector matched a non-write: \`${shape}\``).toBe(false);
    }
  });

  it('⚠️ EVERY WRITER IS CLASSIFIED — locked, or exempt with a reason', () => {
    const unclassified = WRITERS.filter((w) => !w.locked && !(w.file in EXEMPT)).map((w) => w.file);
    expect(
      unclassified,
      'a file writes a `users` row and is neither locked nor exempt — #289 says the ' +
        'set is open, so a new door lands here rather than going unnoticed',
    ).toEqual([]);
  });

  it('⚠️ NO STALE EXEMPTION — an exemption for a file that no longer writes reds', () => {
    // Otherwise the list rots into a permission slip nobody re-reads: a file
    // renamed or made safe keeps its exemption and covers the NEXT thing that
    // moves in under that path.
    const live = new Set(WRITERS.map((w) => w.file));
    expect(Object.keys(EXEMPT).filter((f) => !live.has(f))).toEqual([]);
    // and an exemption must never sit on a file that IS locked — that reads as
    // "we decided not to lock it" about a door that is locked.
    expect(WRITERS.filter((w) => w.locked && w.file in EXEMPT).map((w) => w.file)).toEqual([]);
  });

  it('⚠️ THE COLUMN EXEMPTIONS ARE CHECKED AGAINST THE MIGRATION, not asserted', () => {
    const watched = watchedColumns();
    // POSITIVE CONTROL on the parser: the predicate the migration actually
    // states. If this drifts, every exemption below was judged against a
    // predicate the database does not have.
    expect([...watched].sort()).toEqual(
      ['deactivatedAt', 'isActive', 'practiceId', 'practiceRole', 'softDeletedAt', 'suspendedAt'],
    );

    const offenders: string[] = [];
    for (const w of WRITERS) {
      if (w.locked || w.file === 'src/actions/auth.ts') continue;
      const written = writtenColumns(w.src);
      // NON-VACUITY: a file whose `data:` keys cannot be read would be exempted
      // by a parser failure, which is the quietest way to pass this arm.
      expect(written.length, `${w.file}: no written columns parsed — the arm would be vacuous`)
        .toBeGreaterThan(0);
      for (const c of written) if (watched.has(c)) offenders.push(`${w.file} writes \`${c}\``);
    }
    expect(
      offenders,
      'an exempt door writes a column the trigger predicate reads — it can reach the ' +
        'locking path, so the exemption is void',
    ).toEqual([]);
  });

  it('⚠️ A LOCKED DOOR TAKES THE LOCK BEFORE ITS WRITE — derived over every locked file', () => {
    // The #268 arm, over the derived set rather than the four somebody listed.
    for (const w of WRITERS.filter((x) => x.locked)) {
      const lockAt = w.src.indexOf('withPracticeLock(');
      const writeAt = w.src.search(USER_WRITE);
      expect(lockAt, `${w.file}: imports the lock but never calls it`).toBeGreaterThan(-1);
      expect(
        lockAt,
        `${w.file} writes a user row at ${writeAt} before taking the lock at ${lockAt} — ` +
          'that is the shape measured at 10 deadlocks out of 10',
      ).toBeLessThan(writeAt);
    }
    // NON-VACUITY: the arm above is empty if nothing is locked.
    expect(WRITERS.filter((x) => x.locked).length).toBeGreaterThan(4);
  });

  it('⚠️ ALL FOUR DOORS #289 NAMES ARE LOCKED', () => {
    const named = ['unsuspend', 'force-logout', 'grant-admin', 'revoke-admin'].map(
      (d) => `src/app/api/admin/users/[id]/${d}/route.ts`,
    );
    const locked = new Set(WRITERS.filter((w) => w.locked).map((w) => w.file));
    expect(named.filter((f) => !locked.has(f))).toEqual([]);
  });
});
