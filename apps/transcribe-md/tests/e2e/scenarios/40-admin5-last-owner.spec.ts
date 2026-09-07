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
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

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

/** Where the two scripts live. Each is its OWN FILE — see `race` below. */
const SCRIPTS = mkdtempSync(join(tmpdir(), 'admin5-race-'));

/**
 * The RENDEZVOUS, and it is this harness's overlap witness.
 *
 * ⚠️ ONE BACKEND CANNOT SATISFY IT — BY TWO INDEPENDENT MECHANISMS, AND THE
 * MUTATION MATRIX IS WHY THAT IS STATED CAREFULLY. Each racer waits for the
 * OTHER's `application_name`, and separately excludes its own
 * `pg_backend_pid()`. Either alone is sufficient, so REMOVING EITHER ONE LEAVES
 * THE SEQUENTIAL ARM GREEN — measured, twice, before this comment was written.
 * The arm reds only when BOTH are removed together (a racer waiting for a name
 * it sets itself, without the pid exclusion), and it then fails exactly as it
 * should: *"sequential execution must FAIL — psql should exit non-zero"*.
 *
 * ⚠️ SO DO NOT READ EITHER CLAUSE AS "THE" GUARD. An earlier draft of this
 * comment called the pid exclusion the whole point; that claim was false and
 * the matrix is what caught it. Redundancy here is deliberate — but redundancy
 * is exactly what makes single-mutation proofs come back green, and a proof
 * that cannot red is not a proof. The previous harness
 * asserted "the control reached zero owners" as its proof of overlap — but the
 * unguarded UPDATE is unconditional, so sequential execution reaches zero too.
 * Reaching zero was never a witness of anything.
 *
 * ⚠️ `pg_stat_clear_snapshot()` IS LOAD-BEARING, AND ITS ABSENCE COST A RUN.
 * `pg_stat_activity` is snapshot-cached for the duration of a transaction, so a
 * polling loop without it re-reads its FIRST observation forever. Measured: the
 * peer that happened to announce first waited the full 15s and raised
 * NO_OVERLAP while the other backend was demonstrably alive beside it. A probe
 * answering correctly about a universe that has stopped changing.
 */
function rendezvous(marker: string, peer: string): string {
  return `SET application_name = 'admin5-${marker}';
INSERT INTO admin5_overlap_probe VALUES ('${marker}', pg_backend_pid(), 'announced', clock_timestamp());
DO $$
DECLARE deadline timestamptz := clock_timestamp() + interval '15 seconds';
BEGIN
  LOOP
    EXIT WHEN EXISTS (SELECT 1 FROM pg_stat_activity
                       WHERE application_name = 'admin5-${peer}' AND pid <> pg_backend_pid());
    IF clock_timestamp() > deadline THEN
      RAISE EXCEPTION 'NO_OVERLAP: peer admin5-${peer} never appeared — the two scripts did not run concurrently';
    END IF;
    PERFORM pg_stat_clear_snapshot();
    PERFORM pg_sleep(0.05);
  END LOOP;
END $$;
INSERT INTO admin5_overlap_probe VALUES ('${marker}', pg_backend_pid(), 'entered', clock_timestamp());
`;
}

/** One racer's script, written to its own file. Returns the path. */
function script(marker: string, peer: string, body: string): string {
  const path = join(SCRIPTS, `script-${marker}.sql`);
  writeFileSync(
    path,
    `${rendezvous(marker, peer)}${body}\nINSERT INTO admin5_overlap_probe VALUES ('${marker}', pg_backend_pid(), 'left', clock_timestamp());\n`,
  );
  return path;
}

interface RaceResult { a: string; b: string; rcA: number; rcB: number }

/**
 * Two psql PROCESSES, launched together and awaited, each fed a FILE.
 *
 * ⚠️ THERE IS NO HEREDOC HERE, DELIBERATELY. The shape this replaces built one
 * per racer and put the redirect and the `&` on the TERMINATOR line —
 * `ADMIN5EOF > /tmp/admin5-a.out 2>&1 &` — which is not a delimiter, so bash
 * swallowed the second script, the `wait`, and both capture markers into the
 * FIRST heredoc's body and ran ONE command in the foreground. Reproduced with
 * `cat`: bash warns *"here-document at line 2 delimited by end-of-file"*,
 * neither capture file is created, and the marker split therefore yields two
 * EMPTY strings. Redirects belong on a command line; a script belongs in a file.
 */
function race(pathA: string, pathB: string): RaceResult {
  assertNonProdDbName(DB);
  const outA = join(SCRIPTS, 'a.out');
  const outB = join(SCRIPTS, 'b.out');
  const psql = `${COMPOSE} exec -T postgres psql -U meddoc -d ${DB} -A -t -v ON_ERROR_STOP=1`;
  const rc = execSync(
    `set +e
     ${psql} < ${pathA} > ${outA} 2>&1 &
     PA=$!
     ${psql} < ${pathB} > ${outB} 2>&1 &
     PB=$!
     wait $PA; RA=$?
     wait $PB; RB=$?
     echo "$RA $RB"`,
    { encoding: 'utf8', shell: '/bin/bash', stdio: ['ignore', 'pipe', 'pipe'] },
  ).trim().split(/\s+/);
  return {
    a: readFileSync(outA, 'utf8').trim(),
    b: readFileSync(outB, 'utf8').trim(),
    rcA: Number(rc[0]),
    rcB: Number(rc[1]),
  };
}

/** The same two scripts, run ONE AFTER THE OTHER. The control on the control. */
function sequential(pathA: string, pathB: string): RaceResult {
  assertNonProdDbName(DB);
  const psql = `${COMPOSE} exec -T postgres psql -U meddoc -d ${DB} -A -t -v ON_ERROR_STOP=1`;
  const outA = join(SCRIPTS, 'seq-a.out');
  const outB = join(SCRIPTS, 'seq-b.out');
  const rc = execSync(
    `set +e
     ${psql} < ${pathA} > ${outA} 2>&1; RA=$?
     ${psql} < ${pathB} > ${outB} 2>&1; RB=$?
     echo "$RA $RB"`,
    { encoding: 'utf8', shell: '/bin/bash', stdio: ['ignore', 'pipe', 'pipe'] },
  ).trim().split(/\s+/);
  return {
    a: readFileSync(outA, 'utf8').trim(),
    b: readFileSync(outB, 'utf8').trim(),
    rcA: Number(rc[0]),
    rcB: Number(rc[1]),
  };
}

/**
 * Were the two CRITICAL SECTIONS mutually exclusive?
 *
 * ⚠️ THIS EXISTS BECAUSE THE OUTCOME ASSERTION IS FLAKY AND I MEASURED IT.
 * Deleting `EXECUTE lock_practice` from both racers and re-running THE GUARD
 * caught it in only **1 of 3 runs** (2 of 4 including a first, luckier one).
 * Without the lock the two guarded UPDATEs still race, and whether both
 * evaluate their count subquery before either commits is decided by
 * sub-millisecond scheduling — so `ownersLeft() === 1` passes about half the
 * time on a build with NO LOCK AT ALL.
 *
 * ⚠️ AN INTERMITTENT GUARD IS WORSE THAN AN ABSENT ONE: it goes green in CI,
 * and the reader concludes the lock is proven when what was proven is that
 * Postgres happened to serialise two statements this time.
 *
 * So the lock is witnessed STRUCTURALLY instead. Each racer stamps the moment
 * it holds the lock and the moment it is about to release it; mutual exclusion
 * means those two windows CANNOT overlap. With the lock, B blocks in
 * `lock_practice` until A commits, so B's window starts after A's ends. Without
 * it, both enter immediately and the windows overlap — every time, not half the
 * time.
 */
function criticalSectionsDisjoint(): { disjoint: boolean; rows: string } {
  const overlap = psql(
    `SELECT (SELECT min(at) FROM admin5_overlap_probe WHERE marker='A' AND phase='locked')
          < (SELECT max(at) FROM admin5_overlap_probe WHERE marker='B' AND phase='releasing')
        AND (SELECT min(at) FROM admin5_overlap_probe WHERE marker='B' AND phase='locked')
          < (SELECT max(at) FROM admin5_overlap_probe WHERE marker='A' AND phase='releasing');`,
  );
  const rows = psql(
    `SELECT marker||' '||phase||' '||to_char(at,'HH24:MI:SS.MS')
       FROM admin5_overlap_probe WHERE phase IN ('locked','releasing') ORDER BY at;`,
  );
  return { disjoint: overlap !== 't', rows };
}

/** Did two DISTINCT backends hold overlapping windows? Read from the probe. */
function overlapWitness(): { backends: number; overlapped: boolean; rows: string } {
  const backends = Number(psql(`SELECT count(DISTINCT pid) FROM admin5_overlap_probe;`));
  const overlapped =
    psql(`SELECT (SELECT min(at) FROM admin5_overlap_probe WHERE marker='A' AND phase='entered')
              < (SELECT max(at) FROM admin5_overlap_probe WHERE marker='B' AND phase='left')
            AND (SELECT min(at) FROM admin5_overlap_probe WHERE marker='B' AND phase='entered')
              < (SELECT max(at) FROM admin5_overlap_probe WHERE marker='A' AND phase='left');`) === 't';
  const rows = psql(
    `SELECT marker||' pid='||pid||' '||phase||' '||to_char(at,'HH24:MI:SS.MS')
       FROM admin5_overlap_probe ORDER BY at;`,
  );
  return { backends, overlapped, rows };
}

function seed(): void {
  psql(`
    CREATE TABLE IF NOT EXISTS admin5_overlap_probe
      (marker text, pid int, phase text, at timestamptz);
    TRUNCATE admin5_overlap_probe;
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
  psql(`DELETE FROM users WHERE id IN ('${A}','${B}'); DELETE FROM practices WHERE id='${P}';
         DROP TABLE IF EXISTS admin5_overlap_probe;`);
}

test.describe('⚠️ ADMIN-5 — the last-owner guard, under a real interleaving', () => {
  test.afterAll(() => reap());

  /** The unguarded write — exactly what the code did before ADMIN-5's guard. */
  const plainBody = (target: string) => `BEGIN;
  SELECT count(*) FROM users WHERE "practiceId"='${P}' AND "practiceRole"='OWNER' AND "deactivatedAt" IS NULL;
  SELECT pg_sleep(0.6);
  UPDATE users SET "practiceRole"='CLINICIAN' WHERE id='${target}';
COMMIT;`;

  /** ⚠️ THE SHIPPED STATEMENTS, PREPAREd VERBATIM. If `practice-owner-guard-sql`
   *  changes, this changes with it; nothing here restates the guard. */
  const guardedBody = (marker: string, target: string, role: string) => `PREPARE lock_practice AS ${PRACTICE_LOCK_SQL};
PREPARE change_role AS ${CHANGE_ROLE_GUARDED_SQL};
BEGIN;
  EXECUTE lock_practice('${P}');
  INSERT INTO admin5_overlap_probe VALUES ('${marker}', pg_backend_pid(), 'locked', clock_timestamp());
  SELECT pg_sleep(0.6);
  EXECUTE change_role('${target}', '${P}', '${role}');
  INSERT INTO admin5_overlap_probe VALUES ('${marker}', pg_backend_pid(), 'releasing', clock_timestamp());
COMMIT;`;

  // ══════════════════════════════════════════════════════════════════════════
  // ⚠️ THE CONTROL ON THE CONTROL — ruling #205's hard requirement.
  //
  // A negative control that cannot FAIL is not a control. The harness this
  // replaces asserted "the unguarded race reached zero owners" as its proof of
  // overlap — but the unguarded UPDATE is UNCONDITIONAL, so two sessions run
  // strictly one after the other reach zero as well. It passed all night while
  // nothing raced.
  //
  // This arm runs the SAME TWO SCRIPTS sequentially and requires them to
  // REFUSE. If this ever goes green, the rendezvous has stopped witnessing
  // anything and every other arm in this file is vacuous.
  // ══════════════════════════════════════════════════════════════════════════
  test('⚠️ THE HARNESS WITNESSES OVERLAP — run sequentially, the SAME scripts REFUSE', () => {
    seed();
    expect(ownersLeft(), 'the fixture must start with two owners').toBe(2);

    const { a, b, rcA, rcB } = sequential(
      script('A', 'B', plainBody(A)),
      script('B', 'A', plainBody(B)),
    );

    expect(rcA, 'sequential execution must FAIL — psql should exit non-zero').not.toBe(0);
    expect(rcB).not.toBe(0);
    expect(`${a}\n${b}`, 'the rendezvous must name why it refused').toMatch(/NO_OVERLAP/);
    expect(
      ownersLeft(),
      'the scripts mutated the practice despite never overlapping — the rendezvous is not gating the write',
    ).toBe(2);
  });

  test('⚠️ NEGATIVE CONTROL — the same timing WITHOUT the guard leaves ZERO owners', () => {
    seed();
    expect(ownersLeft(), 'the fixture must start with two owners').toBe(2);

    const { rcA, rcB } = race(
      script('A', 'B', plainBody(A)),
      script('B', 'A', plainBody(B)),
    );
    expect(rcA, 'a racer aborted — see NO_OVERLAP').toBe(0);
    expect(rcB).toBe(0);

    // ⚠️ THE WITNESS IS ASSERTED, NOT INFERRED FROM THE OUTCOME.
    const w = overlapWitness();
    expect(w.backends, `two distinct backends required; probe:\n${w.rows}`).toBe(2);
    expect(w.overlapped, `the two windows did not overlap; probe:\n${w.rows}`).toBe(true);

    expect(
      ownersLeft(),
      'the control did not reproduce the ruled failure — so this file proves nothing',
    ).toBe(0);
  });

  test('⚠️ THE GUARD — the same race leaves the practice with an owner, and refuses the second actor', () => {
    seed();
    expect(ownersLeft()).toBe(2);

    const { a, b, rcA, rcB } = race(
      script('A', 'B', guardedBody('A', A, 'CLINICIAN')),
      script('B', 'A', guardedBody('B', B, 'CLINICIAN')),
    );
    expect(rcA).toBe(0);
    expect(rcB).toBe(0);

    const w = overlapWitness();
    expect(w.backends, `two distinct backends required; probe:\n${w.rows}`).toBe(2);
    expect(w.overlapped, `the two windows did not overlap; probe:\n${w.rows}`).toBe(true);

    // ⚠️ THE LOCK IS WITNESSED STRUCTURALLY, NOT INFERRED FROM THE OUTCOME.
    // Deleting the lock and asserting only `ownersLeft() === 1` caught it in
    // 1 of 3 runs; this catches it every time.
    const cs = criticalSectionsDisjoint();
    expect(
      cs.disjoint,
      `the two critical sections OVERLAPPED — the practice lock is not excluding them:\n${cs.rows}`,
    ).toBe(true);

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

    const demote = `PREPARE lock_practice AS ${PRACTICE_LOCK_SQL};
PREPARE change_role AS ${CHANGE_ROLE_GUARDED_SQL};
BEGIN;
  EXECUTE lock_practice('${P}');
  SELECT pg_sleep(0.6);
  EXECUTE change_role('${A}', '${P}', 'TECH');
COMMIT;`;
    const remove = `PREPARE lock_practice AS ${PRACTICE_LOCK_SQL};
PREPARE remove_member AS ${REMOVE_MEMBER_GUARDED_SQL};
BEGIN;
  EXECUTE lock_practice('${P}');
  SELECT pg_sleep(0.6);
  EXECUTE remove_member('${B}', '${P}', 'admin5-probe-actor');
COMMIT;`;
    const { a, b, rcA, rcB } = race(script('A', 'B', demote), script('B', 'A', remove));
    expect(rcA).toBe(0);
    expect(rcB).toBe(0);
    const w = overlapWitness();
    expect(w.backends, `two distinct backends required; probe:\n${w.rows}`).toBe(2);
    expect(w.overlapped, `the two windows did not overlap; probe:\n${w.rows}`).toBe(true);

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
