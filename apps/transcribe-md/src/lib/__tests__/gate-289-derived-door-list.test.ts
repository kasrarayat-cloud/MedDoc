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
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const APP = join(__dirname, '..', '..', '..');
const MIGRATION = join(
  APP, '..', '..', 'packages', 'db', 'prisma', 'migrations',
  '20260907040000_admin5_last_owner_trigger', 'migration.sql',
);

/**
 * Every write shape that reaches a `users` row — INCLUDING the `as any` cast.
 *
 * ⚠️ ROUND FINDING 3 — THE RECEIVER NAME IS NO LONGER AN ALLOW-LIST. It read
 * `(?:prisma|tx|client|db)`, so a door written as
 * `prisma.$transaction(async (t) => t.user.update({...}))` — a one-letter
 * parameter name — was INVISIBLE, and the gate stayed 7/7 green on a planted,
 * unlocked door that nulls `practiceRole`. Renaming that parameter `t` -> `tx`,
 * changing nothing else, reddened it: the identifier was the whole difference.
 *
 * A client can be bound to any identifier, so the receiver is now ANY
 * identifier. That over-matches by design — a false positive costs a stated
 * exemption, a false negative costs an unlocked door nobody sees.
 */
const USER_WRITE =
  /(?:\(\s*)?[A-Za-z_$][\w$]*\s*\.\s*user\s*(?:as\s+\w+\s*\)\s*)?\.\s*(?:update|updateMany|create|createMany|delete|deleteMany|upsert)\b/;

/**
 * ⚠️ AND RAW SQL IS A DOOR TOO — SAME FINDING. The same planted route rewritten
 * as `prisma.$executeRaw\`UPDATE "users" SET "practiceRole"='CLINICIAN' ...\``
 * also scored 7/7 green. The ORM shape is a convention; the table is the fact.
 */
const RAW_USER_WRITE =
  /\$(?:execute|query)(?:Raw|RawUnsafe)[\s\S]{0,80}?(?:UPDATE|INSERT\s+INTO|DELETE\s+FROM)\s+"?users"?/i;

const stripComments = (s: string) =>
  s
    .split('\n')
    .filter((l) => !l.trimStart().startsWith('//') && !l.trimStart().startsWith('*'))
    .join('\n');

function sourceFiles(): string[] {
  return execFileSync('git', ['ls-files', 'src'], { cwd: APP, encoding: 'utf8' })
    .split('\n')
    // ⚠️ `.tsx` TOO — ROUND FINDING 3. `'use server'` actions are legal in `.tsx`,
    // and this filter excluded the extension outright: a byte-identical file
    // named `.tsx` was invisible at 7/7 green and reddened the moment it was
    // renamed `.ts`. The extension was the whole difference.
    .filter(
      (f) =>
        (f.endsWith('.ts') || f.endsWith('.tsx')) &&
        !f.includes('__tests__') &&
        !f.endsWith('.test.ts') &&
        !f.endsWith('.test.tsx'),
    );
}

/** Files that write a `users` row, derived — never listed. */
function writers(): { file: string; src: string; locked: boolean }[] {
  return sourceFiles()
    .map((file) => ({ file, src: stripComments(readFileSync(join(APP, file), 'utf8')) }))
    .filter((f) => USER_WRITE.test(f.src) || RAW_USER_WRITE.test(f.src))
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

// ════════════════════════════════════════════════════════════════════════════
// ⚠️ THE DERIVATION'S UNIVERSE IS ONE APP, AND THE DATABASE IS SHARED — ROUND
// FINDING 2. NOT HIDDEN, PINNED.
// ════════════════════════════════════════════════════════════════════════════
//
// Everything above derives from `git ls-files src` with `cwd: apps/transcribe-md`
// — 952 files, none of them `apps/meddoc-pro`. That second app talks to the SAME
// database through the SAME `@meddoc/db` client and contains FOUR unlocked
// `users` writers, all of which write predicate columns. The gate is green and
// structurally cannot see any of them.
//
// ⚠️ AND THE MISSING LOCK IS LOAD-BEARING, MEASURED — not argued. Two
// individually legal concurrent writes on a three-owner practice, one through
// transcribe-md's locked `suspend` and one through meddoc-pro's unlocked
// `deactivateUserAction`, produced:
//
//   ERROR: deadlock detected
//   ... waits for ExclusiveLock on advisory lock; blocked by ...
//   CONTEXT: SELECT 1 FROM "users" u WHERE u."practiceId" = OLD."practiceId" ...
//            FOR UPDATE   -- inside users_last_owner_guard()
//
// The LOCKED door lost, and its write silently did not happen — byte-for-byte
// the #268 shape, reinstated by a door the derivation is scoped away from.
//
// ⚠️ THESE CANNOT BE `EXEMPT`, AND THAT IS THE POINT. The exemption list is
// machine-checked against the migration's predicate columns; these four write
// `isActive`, `deactivatedAt` and `practiceRole`, so a prose exemption would be
// rejected by the arm that exists to stop prose exemptions rotting.
//
// So the set is PINNED instead: named, counted, and failing the moment it
// changes in either direction. `meddoc-pro` is decommissioned — its container
// has been `Exited (143)` for five weeks — but it is still a defined service in
// `docker-compose.yml` and one `docker compose up` from live. Whether to lock
// these doors, delete the app, or accept the risk explicitly is not a call this
// gate can make; what it CAN do is stop the risk being invisible.
describe('ruling #289 — the OTHER app writes the same table, and the derivation cannot see it', () => {
  const OTHER_APP = join(APP, '..', 'meddoc-pro');
  /**
   * The unlocked cross-app writers, AS MEASURED — never as remembered.
   *
   * ⚠️ I FIRST PINNED ONE FILE, BECAUSE THE ROUND NAMED FOUR *ACTIONS* AND I
   * READ THAT AS FOUR *DOORS IN ONE FILE*. The derivation says four FILES, and
   * `system-admin/actions.ts` is only the loudest of them. Transcribing a
   * finding's number without re-deriving its subject is how a pin ends up
   * understating exactly the risk it exists to hold still.
   */
  const PINNED = [
    'src/app/dashboard/settings/actions.ts',
    'src/app/system-admin/actions.ts',
    'src/lib/nextauth.ts',
    'src/lib/session-log.ts',
  ];

  it('⚠️ the cross-app unlocked-writer set has not changed — grown OR fixed', () => {
    // ⚠️ DMP-a — the pin retires WITH the app, not before. While
    // `apps/meddoc-pro` exists the set is asserted exactly; once
    // DELETE-MEDDOC-PRO removes it there is nothing to pin and the risk is
    // gone, which is the outcome the pin was filed to reach.
    if (!existsSync(OTHER_APP)) {
      expect(PINNED.length, 'the app is gone — delete PINNED and this arm').toBeGreaterThan(0);
      return;
    }
    const files = execFileSync('git', ['ls-files', 'src'], { cwd: OTHER_APP, encoding: 'utf8' })
      .split('\n')
      .filter((f) => (f.endsWith('.ts') || f.endsWith('.tsx')) && !f.includes('__tests__'));
    const unlocked = files
      .map((file) => ({ file, src: stripComments(readFileSync(join(OTHER_APP, file), 'utf8')) }))
      .filter((f) => USER_WRITE.test(f.src) || RAW_USER_WRITE.test(f.src))
      .filter((f) => !f.src.includes('withPracticeLock'))
      .map((f) => f.file)
      .sort();

    expect(
      unlocked,
      'the cross-app unlocked `users`-writer set moved. If it GREW, a new door ' +
        'can deadlock the locked ones (#268) and nothing else will say so. If it ' +
        'SHRANK, the door was fixed — delete it from PINNED and say so, because a ' +
        'pin that overstates the risk teaches the next reader to discount it.',
    ).toEqual(PINNED);
  });

  it('⚠️ POSITIVE CONTROL — the pin is measuring, not restating itself', () => {
    // DMP-a — retires with the app, exactly as the arm above does.
    if (!existsSync(OTHER_APP)) return;
    // The matcher must actually fire on that file's real content; a pin that
    // passes because the derivation found nothing would be green forever.
    const src = stripComments(readFileSync(join(OTHER_APP, 'src/app/system-admin/actions.ts'), 'utf8'));
    expect(USER_WRITE.test(src), 'the pinned file no longer matches USER_WRITE').toBe(true);
    expect(src.includes('withPracticeLock'), 'the pinned file now takes the lock').toBe(false);
    for (const col of ['isActive', 'deactivatedAt', 'practiceRole']) {
      expect(src, `${col} is no longer written there`).toContain(col);
    }
  });
});
