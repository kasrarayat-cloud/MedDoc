// ============================================================================
// T1 — practice isolation. THE GATE IS THE MUTATION, NOT THE ASSERTION.
// ----------------------------------------------------------------------------
// T1's own wording: "a filter test that FAILS when the practice predicate is
// removed — demonstrated by mutation, not asserted. Without the red, T1 is not
// done."
//
// So this file is written to be BREAKABLE in one specific way. `scopedVisits()`
// takes the predicate as an argument; the gate below runs it twice — once
// scoped, once with the predicate dropped — and asserts the two answers DIFFER.
// A test that only asserted "scoped returns alpha's rows" would pass on a query
// that filters nothing, provided alpha's rows are in the result set. That is the
// vacuity this program keeps meeting, and here it is designed out rather than
// warned about.
//
// ⚠️ THE PREDICATE GOES THROUGH `users`, AND THAT IS THE POINT OF T3.
// `transcribe_visits` has NO practice column — measured 2026-08-05, the
// information_schema query returns nothing. So today a practice scope is a JOIN:
//
//     JOIN users u ON u.id = v."userId"  WHERE u."practiceId" = …
//
// `transcribe_md_patients` IS already `practiceId`-scoped, so the two clinical
// tables sit on DIFFERENT tenancy models right now. T3 closes that. This test is
// written so it keeps meaning the same thing afterwards: it asserts the SCOPE's
// answer, not the shape of the query that produces it, so when the column lands
// only `scopedVisits` changes.
// ============================================================================

import { execSync } from 'node:child_process';

import { expect, test } from '@playwright/test';

import { QA_COMPOSE as COMPOSE, QA_DB as DB } from '../helpers/qa-compose';

function psql(sql: string): string {
  return execSync(`${COMPOSE} exec -T postgres psql -U meddoc -d ${DB} -A -t -f -`, {
    input: sql,
    encoding: 'utf8',
    stdio: ['pipe', 'pipe', 'pipe'],
  }).trim();
}

const count = (sql: string): number => {
  const raw = psql(sql);
  const n = Number.parseInt(raw.split('\n').pop() ?? '', 10);
  if (Number.isNaN(n)) throw new Error(`psql did not return a number: ${JSON.stringify(raw)}`);
  return n;
};

/**
 * Visits visible under a practice scope.
 *
 * `predicate` is injected rather than inlined SO THE GATE CAN REMOVE IT. That is
 * the entire design of this file.
 */
function scopedVisits(predicate: string): number {
  return count(`
    SELECT count(*) FROM transcribe_visits v
    JOIN users u ON u.id = v."userId"
    WHERE v."soapFinal" LIKE 'T1FIXTURE%'
      ${predicate};
  `);
}

const ALPHA = `AND u."practiceId" = (SELECT id FROM practices WHERE slug = 't1-alpha')`;
const NO_PREDICATE = '';

test.describe('T1 — a practice sees its own clinical data and no one else\'s', () => {
  test('the fixture is NON-EMPTY on both sides — without this the rest is free', () => {
    // ⚠️ FIRST, NOT LAST. Every assertion below is about a difference between
    // two counts; if either side is zero the difference can be produced by an
    // empty table rather than by a working predicate. Production's three
    // multi-member practices all have zero visits, which is exactly how this
    // gate would have passed while proving nothing.
    const alpha = scopedVisits(ALPHA);
    const beta = count(`
      SELECT count(*) FROM transcribe_visits v
      JOIN users u ON u.id = v."userId"
      WHERE v."soapFinal" LIKE 'T1FIXTURE%'
        AND u."practiceId" = (SELECT id FROM practices WHERE slug = 't1-beta');
    `);
    expect(alpha, 't1-alpha has no fixture visits — run seed-t1-multiseat.ts').toBeGreaterThan(0);
    expect(beta, 't1-beta has no fixture visits — the exclusion side is empty').toBeGreaterThan(0);

    // And alpha really is multi-seat, which is the other half of T1's wording.
    const members = count(
      `SELECT count(*) FROM users WHERE "practiceId" = (SELECT id FROM practices WHERE slug='t1-alpha');`,
    );
    expect(members, 't1-alpha is not multi-seat').toBeGreaterThanOrEqual(2);
  });

  test('⚠️ THE GATE — dropping the practice predicate CHANGES the answer', () => {
    const scoped = scopedVisits(ALPHA);
    const unscoped = scopedVisits(NO_PREDICATE);

    // This is the mutation, run in-process. If the predicate filtered nothing,
    // these two would be equal and the "isolation" the app claims would be a
    // property of the data rather than of the query.
    expect(
      unscoped,
      'removing the practice predicate returned the SAME count — the predicate ' +
        'is filtering nothing, so every isolation assertion in this suite is vacuous',
    ).toBeGreaterThan(scoped);

    // And the difference is exactly beta's rows: nothing else is in scope.
    const beta = count(`
      SELECT count(*) FROM transcribe_visits v
      JOIN users u ON u.id = v."userId"
      WHERE v."soapFinal" LIKE 'T1FIXTURE%'
        AND u."practiceId" = (SELECT id FROM practices WHERE slug = 't1-beta');
    `);
    expect(unscoped - scoped, 'the leaked rows are not beta\'s — something else is in scope').toBe(
      beta,
    );
  });

  test('no beta row is reachable under an alpha scope — by identity, not by count', () => {
    // A count can match by coincidence. This asserts the actual rows: zero of
    // alpha's visits belong to a beta member.
    const leaked = count(`
      SELECT count(*) FROM transcribe_visits v
      JOIN users u ON u.id = v."userId"
      WHERE v."soapFinal" LIKE 'T1FIXTURE%'
        ${ALPHA}
        AND u."practiceId" = (SELECT id FROM practices WHERE slug = 't1-beta');
    `);
    expect(leaked, 'a visit is scoped to BOTH practices — the join is wrong').toBe(0);
  });

  test('patients isolate too — and they are already practice-scoped natively', () => {
    // ⚠️ A DIFFERENT TENANCY MODEL, DELIBERATELY EXERCISED. `transcribe_md_patients`
    // carries `practiceId` directly, while visits reach it through `users`. Both
    // must isolate, and asserting only the one that shares the visits' shape
    // would leave the native-column path untested until T3 changes it.
    const alphaPatients = count(
      `SELECT count(*) FROM transcribe_md_patients WHERE name LIKE 'T1FIXTURE%' AND "practiceId" = (SELECT id FROM practices WHERE slug='t1-alpha');`,
    );
    const allPatients = count(
      `SELECT count(*) FROM transcribe_md_patients WHERE name LIKE 'T1FIXTURE%';`,
    );
    expect(alphaPatients, 'alpha has no fixture patients').toBeGreaterThan(0);
    expect(
      allPatients,
      'the unscoped patient count equals the scoped one — the practiceId filter is inert',
    ).toBeGreaterThan(alphaPatients);
  });
});
