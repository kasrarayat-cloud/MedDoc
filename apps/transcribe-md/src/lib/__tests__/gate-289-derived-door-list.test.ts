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
//
// ⚠️ ROUND SIX, 2026-09-10 — THE PIN WAS KEYED ON A DIRECTORY NAME, AND A
// RENAME READ AS A DELETION. The DMP-a form read `git ls-files src` inside
// `join(APP, '..', 'meddoc-pro')` and returned EARLY when that path did not
// exist. MEASURED: `git mv apps/meddoc-pro apps/crm-legacy` — all four unlocked
// writers still tracked, still unlocked — left BOTH arms green in 0ms and 1ms by
// early return, where origin/main's form red (ENOENT). The absent branch's one
// assertion, `PINNED.length > 0` on a four-element literal, could not fail, so
// its message "delete PINNED and this arm" was never enforced. **A missing path
// is not a deleted writer.**
//
// So the pin is now keyed on the WRITERS, wherever they live: the universe is
// every tracked non-test source OUTSIDE this app — the exact complement of the
// derivation above — compared EXACTLY, by repo-relative path. A rename moves
// the paths: red. A move into `packages/` adds an unlisted path: red. A
// deletion drops the CRM's seven rows: red, until the deletion PR deletes them
// in the same change — the DELETE-MEDDOC-PRO row's own words, "the pin retires
// WITH this row and not before", now enforced rather than assumed. There is no
// early return left for anything to fall through.
//
// ⚠️ NOT WATCHED HERE, SAID SO THE NAME DOES NOT READ WIDER THAN THE SET: this
// app's OWN non-`src/` files. Measured 2026-09-10, seven unlocked `users`
// writers live in `apps/transcribe-md/scripts/` (QA walks, seed scripts and
// `prod-smoke/provision.ts`). They are a gap in the derivation ABOVE, not a
// cross-app door, and are filed in RELAY rather than folded in here.
describe('ruling #289 — the OTHER app writes the same table, and the derivation cannot see it', () => {
  const REPO = join(APP, '..', '..');
  const isTestPath = (f: string) => /(^|\/)__tests__\//.test(f) || /\.(test|spec)\.tsx?$/.test(f);

  /** The complement of the derivation above: tracked, non-test, outside this app. */
  function outsideSources(): string[] {
    return execFileSync('git', ['ls-files', '-z', '--', '*.ts', '*.tsx'], { cwd: REPO, encoding: 'utf8' })
      .split('\0')
      .filter((f) => f && !f.startsWith('apps/transcribe-md/') && !isTestPath(f));
  }

  /** Unlocked `users` writers among the given sources — pure, so it can be planted. */
  function unlockedWriters(files: { file: string; src: string }[]): string[] {
    return files
      .filter((f) => !isTestPath(f.file))
      .map((f) => ({ file: f.file, src: stripComments(f.src) }))
      .filter((f) => USER_WRITE.test(f.src) || RAW_USER_WRITE.test(f.src))
      .filter((f) => !f.src.includes('withPracticeLock'))
      .map((f) => f.file)
      .sort();
  }

  /**
   * Every unlocked `users` writer outside this app, AS MEASURED — never as
   * remembered. `door: true` rows are ruling #289's pin.
   *
   * ⚠️ I FIRST PINNED ONE FILE, BECAUSE THE ROUND NAMED FOUR *ACTIONS* AND I
   * READ THAT AS FOUR *DOORS IN ONE FILE*. The derivation says four FILES, and
   * `system-admin/actions.ts` is only the loudest of them. Transcribing a
   * finding's number without re-deriving its subject is how a pin ends up
   * understating exactly the risk it exists to hold still.
   *
   * ⚠️ MEASURED 2026-09-10 AND DELIBERATELY NOT ACTED ON: by this file's own
   * `writtenColumns` parser, only `system-admin/actions.ts` writes a predicate
   * column (`isActive`, `deactivatedAt`, `practiceRole`, `practiceId`); the
   * other three write `name`, `failedLoginCount/lockedUntil/lastLogin` and
   * `lastLoginIp`. The pin's recorded criterion is "unlocked `users` writer",
   * so all four stay pinned. Whether three of them could deadlock is a question
   * for the console PORT, which must port every one of them under
   * `withPracticeLock` regardless.
   */
  const CROSS_APP_UNLOCKED: Record<string, { door: boolean; reason: string; retires: string; checkColumns?: true }> = {
    'apps/meddoc-pro/src/app/dashboard/settings/actions.ts': { door: true, reason: 'ruling #289 pin', retires: 'DELETE-MEDDOC-PRO' },
    'apps/meddoc-pro/src/app/system-admin/actions.ts': { door: true, reason: 'ruling #289 pin — the measured deadlock door', retires: 'DELETE-MEDDOC-PRO' },
    'apps/meddoc-pro/src/lib/nextauth.ts': { door: true, reason: 'ruling #289 pin', retires: 'DELETE-MEDDOC-PRO' },
    'apps/meddoc-pro/src/lib/session-log.ts': { door: true, reason: 'ruling #289 pin', retires: 'DELETE-MEDDOC-PRO' },
    'apps/meddoc-pro/scripts/seed-admin.ts': {
      door: false, reason: 'CRM seed script, run by hand against a dev/test database; never a runtime door', retires: 'DELETE-MEDDOC-PRO',
    },
    'apps/meddoc-pro/scripts/seed-e2e-admin.ts': {
      door: false, reason: 'CRM seed script, run by hand against a dev/test database; never a runtime door', retires: 'DELETE-MEDDOC-PRO',
    },
    'apps/meddoc-pro/scripts/seed-tenancy-fixtures.ts': {
      door: false, reason: 'CRM seed script, run by hand against a dev/test database; never a runtime door', retires: 'DELETE-MEDDOC-PRO',
    },
    'packages/auth/src/index.ts': {
      door: false,
      reason:
        '⚠️ a SHARED package transcribe-md imports at RUNTIME, and invisible to the derivation above, which reads ' +
        'apps/transcribe-md/src only. It writes `mfaBackupCodes` — no predicate column, and that is CHECKED below, ' +
        'not asserted, so the day it writes one this row reds.',
      retires: 'never with the CRM — it is shared',
      checkColumns: true,
    },
    'scripts/qa/rc2-twin-door-on-qa.ts': {
      door: false, reason: 'the RC-2 QA walk (raw SQL), run by hand against the isolated QA stack; not a runtime door', retires: 'never with the CRM',
    },
  };

  it('⚠️ the unlocked-writer set outside this app is EXACTLY the filed set — keyed on the writers, never on a directory name', () => {
    const universe = outsideSources();
    const unlocked = unlockedWriters(universe.map((file) => ({ file, src: readFileSync(join(REPO, file), 'utf8') })));
    expect(
      unlocked,
      'the unlocked `users`-writer set outside apps/transcribe-md moved. If a path is NEW, a door can deadlock ' +
        'the locked ones (#268) and nothing else will say so — and a RENAMED or MOVED app arrives here as a ' +
        'new path, not as a deletion. If a row is GONE, the writer was fixed or deleted: delete its row in the ' +
        'same change and say which. DELETE-MEDDOC-PRO reds this on purpose — the pin retires WITH the app, by edit.',
    ).toEqual(Object.keys(CROSS_APP_UNLOCKED).sort());
  });

  it('⚠️ POSITIVE CONTROL — the universe is the whole repo outside this app, not one directory', () => {
    // Derived independently of the writer filter: the population it scans.
    const universe = outsideSources();
    expect(universe.length, 'the scan universe is nearly empty — every arm here is vacuous').toBeGreaterThan(100);
    const tops = new Set(universe.map((f) => f.split('/')[0]));
    for (const top of ['apps', 'packages', 'scripts']) {
      expect(tops.has(top), `the universe does not reach ${top}/ — it is scoped, not derived`).toBe(true);
    }
    expect(universe.some((f) => f.startsWith('apps/transcribe-md/')), 'the universe includes this app — it is not the complement').toBe(false);
  });

  it('⚠️ POSITIVE CONTROL — the filter is measuring, not restating itself', () => {
    // Planted, so it cannot decay when the CRM's rows retire. A pin that passes
    // because the filter found nothing would be green forever.
    const planted = unlockedWriters([
      { file: 'packages/x/door.ts', src: 'await (prisma.user as any).update({ data: { isActive: false } });' },
      { file: 'packages/x/raw.ts', src: 'await prisma.$executeRawUnsafe(`UPDATE "users" SET "practiceRole" = $1`, r);' },
      { file: 'packages/x/locked.ts', src: 'await withPracticeLock(tx, id, async () => tx.user.update({ data: {} }));' },
      { file: 'packages/x/__tests__/t.ts', src: 'await prisma.user.update({ data: { isActive: false } });' },
      { file: 'packages/x/read.ts', src: 'await prisma.user.findUnique({ where: { id } });' },
    ]);
    expect(planted).toEqual(['packages/x/door.ts', 'packages/x/raw.ts']);
    // and on real content, for every pinned door still in the tree
    for (const [file, row] of Object.entries(CROSS_APP_UNLOCKED)) {
      if (!row.door) continue;
      const src = stripComments(readFileSync(join(REPO, file), 'utf8'));
      expect(USER_WRITE.test(src) || RAW_USER_WRITE.test(src), `${file} no longer matches the writer shapes`).toBe(true);
    }
    const loudest = 'apps/meddoc-pro/src/app/system-admin/actions.ts';
    if (loudest in CROSS_APP_UNLOCKED) {
      const src = stripComments(readFileSync(join(REPO, loudest), 'utf8'));
      for (const col of ['isActive', 'deactivatedAt', 'practiceRole']) {
        expect(src, `${col} is no longer written there`).toContain(col);
      }
    }
  });

  it('⚠️ A FILED NON-DOOR ON A RUNTIME PATH WRITES NO PREDICATE COLUMN — checked against the migration', () => {
    const watched = watchedColumns();
    const rows = Object.entries(CROSS_APP_UNLOCKED).filter(([, r]) => r.checkColumns);
    expect(rows.length, 'no row is column-checked — this arm is vacuous').toBeGreaterThan(0);
    for (const [file] of rows) {
      const written = writtenColumns(stripComments(readFileSync(join(REPO, file), 'utf8')));
      expect(written.length, `${file}: no written columns parsed — the check would be vacuous`).toBeGreaterThan(0);
      expect(written.filter((c) => watched.has(c)), `${file} now writes a predicate column — it is a DOOR`).toEqual([]);
    }
  });
});
