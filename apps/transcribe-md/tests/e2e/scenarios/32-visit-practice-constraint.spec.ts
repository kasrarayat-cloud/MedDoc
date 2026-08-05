// ============================================================================
// T3 — a cross-practice visit is UNREPRESENTABLE, not merely discouraged.
// ----------------------------------------------------------------------------
// T3's gate: "a DB-level constraint or trigger that makes a cross-practice visit
// impossible, proven by attempting one."
//
// So this file ATTEMPTS one. It is not a check that a constraint is listed in
// `pg_constraint` — that would prove the constraint exists, not that it bites.
//
// ⚠️ THE MECHANISM IS A COMPOSITE FK, NOT A TRIGGER, AND THE DIFFERENCE MATTERS.
//   transcribe_visits(patientId, practiceId)
//     → transcribe_md_patients(id, practiceId)
// A trigger can be disabled, skipped by a bulk load, or dropped in a restore. A
// composite FK makes the bad row unrepresentable: there is no (id, practiceId)
// pair to reference, so the storage layer refuses it. Application code cannot
// route around it because there is nothing to route around.
//
// ⚠️ THE POSITIVE CONTROL IS NOT OPTIONAL. "The insert failed" proves nothing on
// its own — a typo'd column name fails too, and so does a missing user. The
// control runs the SAME insert with the CORRECT practice and requires it to
// SUCCEED. Only the pair shows the constraint rejects the wrong tenant
// specifically rather than rejecting everything.
// ============================================================================

import { execSync } from 'node:child_process';

import { expect, test } from '@playwright/test';

import { QA_COMPOSE as COMPOSE, QA_DB as DB } from '../helpers/qa-compose';

/** Runs SQL, returning { ok, out }. Never throws — the failure IS the datum. */
function trySql(sql: string): { ok: boolean; out: string } {
  try {
    const out = execSync(
      `${COMPOSE} exec -T postgres psql -U meddoc -d ${DB} -v ON_ERROR_STOP=1 -A -t -f -`,
      { input: sql, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] },
    );
    return { ok: true, out: String(out) };
  } catch (err) {
    const e = err as { stdout?: string; stderr?: string };
    return { ok: false, out: `${e.stdout ?? ''}${e.stderr ?? ''}` };
  }
}

const cleanup = () =>
  trySql(`DELETE FROM transcribe_visits WHERE id IN ('t3-attack','t3-control');`);

/** The same insert both ways — only `practiceId` differs. */
const insertVisit = (id: string, practiceExpr: string) => `
  INSERT INTO transcribe_visits
    (id,"userId","patientId",specialty,"inputMode","practiceId","createdBy","updatedAt","createdAt")
  SELECT '${id}', u.id, p.id, 'primary-care', 'text_notes', ${practiceExpr}, u.id, now(), now()
  FROM transcribe_md_patients p
  CROSS JOIN LATERAL (SELECT id FROM users LIMIT 1) u
  LIMIT 1;
`;

test.describe('T3 — the visit/patient tenant cannot diverge', () => {
  test.afterEach(() => {
    cleanup();
  });

  test('the composite FK exists and the column is NOT NULL', () => {
    const fk = trySql(
      `SELECT 1 FROM pg_constraint WHERE conname='transcribe_visits_patientId_practiceId_fkey';`,
    );
    expect(fk.ok && fk.out.trim() === '1', 'the composite FK is missing').toBe(true);

    const nn = trySql(
      `SELECT is_nullable FROM information_schema.columns WHERE table_name='transcribe_visits' AND column_name='practiceId';`,
    );
    expect(nn.out.trim(), 'practiceId is nullable — the backfill or SET NOT NULL did not land').toBe(
      'NO',
    );
  });

  test('every existing visit agrees with its patient — 0 mismatches', () => {
    const r = trySql(`
      SELECT count(*) FROM transcribe_visits v
      JOIN transcribe_md_patients p ON p.id = v."patientId"
      WHERE v."practiceId" <> p."practiceId";
    `);
    expect(Number.parseInt(r.out.trim(), 10), 'a visit disagrees with its patient').toBe(0);

    // Non-vacuity: there ARE visits to disagree.
    const n = trySql(`SELECT count(*) FROM transcribe_visits;`);
    expect(
      Number.parseInt(n.out.trim(), 10),
      'no visits at all — the mismatch check above is free',
    ).toBeGreaterThan(0);
  });

  test('⚠️ THE GATE — a cross-practice visit is REFUSED by the database', () => {
    cleanup();
    const attack = trySql(
      insertVisit('t3-attack', `(SELECT id FROM practices WHERE id <> p."practiceId" LIMIT 1)`),
    );
    expect(
      attack.ok,
      'a visit whose practice differs from its patient\'s was ACCEPTED — the ' +
        'tenant guarantee does not exist',
    ).toBe(false);
    // And refused for the RIGHT reason, not incidentally.
    expect(attack.out).toContain('transcribe_visits_patientId_practiceId_fkey');
  });

  test('POSITIVE CONTROL — the same insert with the correct practice SUCCEEDS', () => {
    // Without this, the test above passes on a broken query, a missing table,
    // or a dropped user — every one of which also "fails to insert".
    cleanup();
    const ok = trySql(insertVisit('t3-control', `p."practiceId"`));
    expect(
      ok.ok,
      'the control insert failed too — the refusal above proves nothing about ' +
        'tenancy, only that this INSERT does not work',
    ).toBe(true);
  });
});
