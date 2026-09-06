// ============================================================================
// ADMIN-5 — THE CONCURRENT PROOF.
// ----------------------------------------------------------------------------
// ⚠️ THIS IS THE ARM THE ADMIN-5 ROW DEMANDS BY NAME: "a proof arm drives the
// CONCURRENT case rather than the sequential one". A sequential test of a
// last-owner guard is not a weaker proof of the same thing — it is a proof of a
// different thing. The interleaving ruling #195 names is invisible to it BY
// CONSTRUCTION:
//
//   two owners are demoted at the same instant, `SELECT count(*) WHERE
//   practiceRole='OWNER'` returns 2 to BOTH actors, both conclude "there is
//   another owner", both write, and the practice is left with ZERO owners.
//
// Run the same two operations one after the other and the second one correctly
// sees 1 and refuses. The sequential test passes against a guard that does not
// work.
//
// ⚠️ IT RUNS THE SHIPPED SQL, NOT A COPY OF IT. The statements are imported
// from `src/lib/practice-owner-guard-sql` — a module with NO imports, written
// that way for exactly this — and handed to Postgres with `PREPARE`, which
// accepts the same `$1/$2/$3` placeholders the server binds. A proof that
// retypes the SQL it is checking proves the author can type the same thing
// twice: it goes green against a guard that was never shipped, and it STAYS
// green when the shipped guard changes.
//
// ⚠️ AND IT CARRIES ITS OWN NEGATIVE CONTROL, WHICH IS NOT OPTIONAL. The
// guarded arm going green proves nothing unless the identical timing, against
// an UNGUARDED statement, can be shown to produce the wrong answer. It can:
// the control leaves the practice with zero owners. Without it this file would
// pass against a probe whose two sessions never actually overlapped.
//
// WHY psql AND NOT PRISMA: this repository's E2E process deliberately cannot
// load Prisma — `helpers/cleanup.ts` reaches the database through
// `docker compose exec postgres psql` so the test process does not depend on
// `@meddoc/db` compiling or on loading a `.env`. That is a constraint, not a
// preference, and it is why the SQL had to become shared data.
//
// ⚠️ WHAT THIS FILE DOES NOT PROVE, SAID PLAINLY. It proves the STATEMENTS are
// correct under a real interleaving. It does not prove the TypeScript wraps
// them correctly — that `withPracticeLock` opens a transaction, that the
// parameters are passed in the right order, that the outcomes map to the right
// refusals. Those are `src/lib/__tests__/gate-admin5-owner-guard.test.ts`,
// which mocks Prisma and says so in its own header. Neither file alone covers
// the path; the split is stated in both rather than implied away in either.
// ============================================================================

import { execSync } from 'node:child_process';

import { expect, test } from '@playwright/test';

import { assertNonProdDbName } from '@meddoc/db/guard';

import {
  CHANGE_ROLE_GUARDED_SQL,
  PRACTICE_LOCK_SQL,
  REMOVE_MEMBER_GUARDED_SQL,
} from '../../../src/lib/practice-owner-guard-sql';
import { QA_COMPOSE as COMPOSE, QA_DB as DB } from '../helpers/qa-compose';

const P = 'admin5-probe-practice';
const A = 'admin5-probe-owner-a';
const B = 'admin5-probe-owner-b';

/** One psql invocation. Returns trimmed stdout. */
function psql(sql: string): string {
  // FAIL-CLOSED. The db-guard refuses anything not positively a non-prod
  // database, and this file writes.
  assertNonProdDbName(DB);
  return execSync(
    `${COMPOSE} exec -T postgres psql -U meddoc -d ${DB} -A -t -v ON_ERROR_STOP=0`,
    { input: sql, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] },
  ).trim();
}

/** Two psql sessions, started together, each fed a script. Returns both
 *  transcripts. The overlap is produced by `sleep` inside the SQL, so the
 *  interleaving does not depend on this process's scheduling. */
function race(scriptA: string, scriptB: string): { a: string; b: string } {
  const one = (sql: string) =>
    new Promise<string>((resolve) => {
      try {
        resolve(psql(sql));
      } catch (err) {
        // A serialization or constraint failure is a RESULT here, not a crash.
        resolve(String((err as { stderr?: Buffer }).stderr ?? err));
      }
    });
  // execSync is blocking, so the two must be launched as detached shells and
  // joined. `&` plus `wait` in one shell gives genuine overlap.
  const script = (sql: string) =>
    `${COMPOSE} exec -T postgres psql -U meddoc -d ${DB} -A -t <<'ADMIN5EOF'\n${sql}\nADMIN5EOF`;
  const out = execSync(
    `set +e
     ${script(scriptA)} > /tmp/admin5-a.out 2>&1 &
     PA=$!
     ${script(scriptB)} > /tmp/admin5-b.out 2>&1 &
     PB=$!
     wait $PA; wait $PB
     echo "===A==="; cat /tmp/admin5-a.out; echo "===B==="; cat /tmp/admin5-b.out`,
    { encoding: 'utf8', shell: '/bin/bash', stdio: ['ignore', 'pipe', 'pipe'] },
  );
  void one;
  const [, a = '', b = ''] = out.split(/===[AB]===/);
  return { a: a.trim(), b: b.trim() };
}

function seed(): void {
  psql(`
    DELETE FROM users WHERE id IN ('${A}','${B}');
    DELETE FROM practices WHERE id = '${P}';
    INSERT INTO practices (id, slug, name, "createdAt", "updatedAt")
      VALUES ('${P}', '${P}', 'ADMIN-5 probe', now(), now());
    INSERT INTO users (id, email, name, "passwordHash", "practiceId", "practiceRole",
                       "isActive", role, "createdAt", "updatedAt")
      VALUES ('${A}', '${A}@admin5.invalid', 'Probe A', 'x', '${P}', 'OWNER', true, 'STAFF', now(), now()),
             ('${B}', '${B}@admin5.invalid', 'Probe B', 'x', '${P}', 'OWNER', true, 'STAFF', now(), now());
  `);
}

function ownersLeft(): number {
  return Number(
    psql(
      `SELECT count(*) FROM users WHERE "practiceId"='${P}'
         AND "practiceRole"='OWNER' AND "deactivatedAt" IS NULL;`,
    ),
  );
}

function reap(): void {
  psql(`DELETE FROM users WHERE id IN ('${A}','${B}'); DELETE FROM practices WHERE id='${P}';`);
}

test.describe('⚠️ ADMIN-5 — the last-owner guard, under a real interleaving', () => {
  test.afterAll(() => reap());

  test('⚠️ NEGATIVE CONTROL — the same timing WITHOUT the guard leaves ZERO owners', () => {
    seed();
    expect(ownersLeft(), 'the fixture must start with two owners').toBe(2);

    // The unguarded write: exactly what the code did before ADMIN-5's guard,
    // with the same overlap. If this does NOT reach zero, the two sessions did
    // not overlap and every other assertion in this file is vacuous.
    const plain = (target: string) => `
      BEGIN;
      SELECT count(*) FROM users WHERE "practiceId"='${P}' AND "practiceRole"='OWNER' AND "deactivatedAt" IS NULL;
      SELECT pg_sleep(0.6);
      UPDATE users SET "practiceRole"='CLINICIAN' WHERE id='${target}';
      COMMIT;`;
    race(plain(A), plain(B));

    expect(
      ownersLeft(),
      'the control did not reproduce the ruled failure — the sessions did not overlap, so this file proves nothing',
    ).toBe(0);
  });

  test('⚠️ THE GUARD — the same race leaves the practice with an owner, and refuses the second actor', () => {
    seed();
    expect(ownersLeft()).toBe(2);

    // ⚠️ THE SHIPPED STATEMENTS, PREPAREd VERBATIM. If `practice-owner-guard-sql`
    // changes, this changes with it; nothing here restates the guard.
    const guarded = (target: string) => `
      BEGIN;
      PREPARE lock_practice AS ${PRACTICE_LOCK_SQL};
      PREPARE change_role AS ${CHANGE_ROLE_GUARDED_SQL};
      EXECUTE lock_practice('${P}');
      SELECT pg_sleep(0.6);
      EXECUTE change_role('${target}', '${P}', 'CLINICIAN');
      COMMIT;`;
    const { a, b } = race(guarded(A), guarded(B));

    // ⚠️ THE INVARIANT IS THE ASSERTION. Which of the two won is a race and must
    // not be asserted; that exactly one did is the property.
    expect(
      ownersLeft(),
      'the practice was left with no owner — the guard did not hold under concurrency',
    ).toBe(1);

    // And the loser was REFUSED rather than erroring: `UPDATE 0`, not a
    // serialization failure. That is the difference between telling a doctor
    // "this is the last owner" and telling them "try again".
    const both = `${a}\n${b}`;
    expect(both, 'expected one UPDATE 1 and one UPDATE 0').toMatch(/UPDATE 1/);
    expect(both).toMatch(/UPDATE 0/);
    expect(both, 'a serialization failure means the shape is not the one that shipped').not.toMatch(
      /could not serialize/i,
    );
  });

  test('⚠️ THE CROSS-DOOR RACE — one actor DEMOTES while another REMOVES', () => {
    // ⚠️ THE ARM A PER-DOOR GUARD PASSES AND A CORRECT ONE EARNS. Demotion and
    // removal are two doors to ONE invariant, and a build that guards each door
    // against ITSELF still loses the practice when the two race each other:
    // A demotes owner-1 while B removes owner-2, each sees the other as proof
    // that an owner remains, and the practice ends with none.
    //
    // It holds here for a structural reason rather than a lucky one: both doors
    // take the SAME practice lock, so they cannot overlap at all — which is
    // exactly why the lock is on `practices` and not on the user rows.
    seed();
    expect(ownersLeft()).toBe(2);

    const demote = `
      BEGIN;
      PREPARE lock_practice AS ${PRACTICE_LOCK_SQL};
      PREPARE change_role AS ${CHANGE_ROLE_GUARDED_SQL};
      EXECUTE lock_practice('${P}');
      SELECT pg_sleep(0.6);
      EXECUTE change_role('${A}', '${P}', 'TECH');
      COMMIT;`;
    const remove = `
      BEGIN;
      PREPARE lock_practice AS ${PRACTICE_LOCK_SQL};
      PREPARE remove_member AS ${REMOVE_MEMBER_GUARDED_SQL};
      EXECUTE lock_practice('${P}');
      SELECT pg_sleep(0.6);
      EXECUTE remove_member('${B}', '${P}', 'admin5-probe-actor');
      COMMIT;`;
    const { a, b } = race(demote, remove);

    expect(
      ownersLeft(),
      'a demotion and a removal raced each other to zero owners — the two doors are not sharing one guard',
    ).toBe(1);
    const both = `${a}\n${b}`;
    expect(both).toMatch(/UPDATE 1/);
    expect(both).toMatch(/UPDATE 0/);
  });

  test('⚠️ a practice with TWO owners still lets one of them go — the guard is not a wall', () => {
    seed();
    // Sequentially, with two owners, the first demotion MUST succeed. A guard
    // that refuses this refuses the whole feature while looking correct on the
    // race above.
    const out = psql(`
      BEGIN;
      PREPARE lock_practice AS ${PRACTICE_LOCK_SQL};
      PREPARE change_role AS ${CHANGE_ROLE_GUARDED_SQL};
      EXECUTE lock_practice('${P}');
      EXECUTE change_role('${A}', '${P}', 'CLINICIAN');
      COMMIT;`);
    expect(out).toMatch(/UPDATE 1/);
    expect(ownersLeft()).toBe(1);

    // …and the LAST one is then refused, by the database, with no arithmetic.
    const out2 = psql(`
      BEGIN;
      PREPARE lock_practice AS ${PRACTICE_LOCK_SQL};
      PREPARE change_role AS ${CHANGE_ROLE_GUARDED_SQL};
      EXECUTE lock_practice('${P}');
      EXECUTE change_role('${B}', '${P}', 'CLINICIAN');
      COMMIT;`);
    expect(out2).toMatch(/UPDATE 0/);
    expect(ownersLeft()).toBe(1);
  });
});
