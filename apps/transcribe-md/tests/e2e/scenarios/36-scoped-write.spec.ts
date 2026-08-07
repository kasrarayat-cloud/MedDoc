// ============================================================================
// T5-W — a practice-scoped WRITE, proven by attempt in BOTH directions.
// ----------------------------------------------------------------------------
// ⚠️ WHY BOTH DIRECTIONS ARE MANDATORY HERE, AND NOT MERELY THOROUGH.
//
// `update` throws when no row matches. `updateMany` returns `{ count: 0 }` — no
// error, no exception, a SUCCESSFUL CALL THAT DID NOTHING. Several call sites in
// this codebase already read `count === 0` as "a concurrent write won", so a
// predicate that matches nothing wears the benign-race costume perfectly.
//
//   REFUSAL-ONLY PROOF   satisfied by a predicate matching NOTHING — which is
//                        the exact failure it was meant to exclude.
//   POSITIVE PROOF       is what distinguishes "refused the wrong tenant" from
//                        "refuses everyone, including the right one".
//
// A leaked WRITE is not a leaked read. A disclosure is bad; a false entry in
// another practice's chart is a clinical record saying something no clinician
// wrote, found — if it is ever found — by someone reading their own note and not
// recognising it.
//
// ⚠️ EVERY MUTATION HERE IS TRANSACTIONAL OR REVERTED. The rule was earned on
// 2026-08-05, when a mutation proof dropped a constraint, nulled 21 signers, and
// left the database in the exact state the test existed to prove impossible.
// ============================================================================

import { execSync } from 'node:child_process';

import { expect, test } from '@playwright/test';

import { QA_COMPOSE as COMPOSE, QA_DB as DB } from '../helpers/qa-compose';
import { loginUser } from '../helpers/auth';

const ALPHA_1 = 't1-alpha-1@t1.invalid'; // OWNER of alpha, author of its visits
const BETA_1 = 't1-beta-1@t1.invalid'; // another practice entirely

const MEMBER_PASSWORD = process.env.T1_MEMBER_PASSWORD ?? '';

function sql(query: string): string {
  return String(
    execSync(`${COMPOSE} exec -T postgres psql -U meddoc -d ${DB} -v ON_ERROR_STOP=1 -A -t -f -`, {
      input: query,
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
    }),
  ).trim();
}

/**
 * An UNARCHIVED, **SIGNED** alpha visit.
 *
 * ⚠️ SIGNED IS NOT INCIDENTAL. `POST /archive` refuses a non-signed visit with
 * 400 VISIT_NOT_SIGNED — HIPAA retention forbids hard-deleting a signed note, so
 * archive is the signed-note path and delete is the draft path. The first
 * version of this file picked any unarchived visit and the POSITIVE half failed
 * on that 400.
 *
 * Which is the point of having a positive half: a refusal-only proof would have
 * been perfectly green while the fixture was wrong, and would have stayed green
 * if the predicate matched nothing at all.
 */
function alphaVisit(): string {
  return sql(`
    SELECT v.id FROM transcribe_visits v
    JOIN users u ON u.id = v."userId"
    WHERE u.email = '${ALPHA_1}'
      AND v."signedAt" IS NOT NULL
      AND v."deletedAt" IS NULL AND v."archivedAt" IS NULL
    ORDER BY v."createdAt" DESC LIMIT 1;
  `);
}

const TOUCHED: string[] = [];

test.describe('T5-W — the scoped write refuses the wrong tenant AND serves the right one', () => {
  test.beforeAll(() => {
    expect(MEMBER_PASSWORD.length, 'T1_MEMBER_PASSWORD is unset').toBeGreaterThan(0);
    // NON-VACUITY: there is a visit, and the two members really are in different
    // practices — otherwise "beta is refused" passes for the wrong reason.
    expect(
      alphaVisit().length,
      'no SIGNED, unarchived alpha visit — archive refuses anything else with 400',
    ).toBeGreaterThan(0);
    const cross = sql(`
      SELECT count(*) FROM users a, users b
      WHERE a.email='${ALPHA_1}' AND b.email='${BETA_1}' AND a."practiceId" = b."practiceId";`);
    expect(cross, 'alpha and beta share a practice — the refusal below is meaningless').toBe('0');
  });

  test.afterAll(() => {
    for (const id of TOUCHED) {
      sql(`UPDATE transcribe_visits SET "archivedAt" = NULL WHERE id = '${id}';`);
    }
  });

  test('⚠️ REFUSED — a member of another practice cannot archive the visit', async ({ page }) => {
    const visitId = alphaVisit();
    const before = sql(`SELECT COALESCE("archivedAt"::text,'-') FROM transcribe_visits WHERE id='${visitId}';`);

    await loginUser(page, BETA_1, MEMBER_PASSWORD);
    const res = await page.request.post(`/api/visits/${visitId}/archive`, { data: {} });

    expect(res.status(), 'a cross-practice archive was not refused').toBe(404);

    // ⚠️ AND THE ROW IS UNCHANGED. The status code says the ROUTE refused; only
    // the row says the WRITE did not happen. A route that 404s after mutating
    // would pass the assertion above and still have altered another practice's
    // chart.
    const after = sql(`SELECT COALESCE("archivedAt"::text,'-') FROM transcribe_visits WHERE id='${visitId}';`);
    expect(after, 'the row changed despite the refusal').toBe(before);
  });

  test('⚠️ SERVED — the owning practice CAN archive it (the count-0 half)', async ({ page }) => {
    const visitId = alphaVisit();
    TOUCHED.push(visitId);

    await loginUser(page, ALPHA_1, MEMBER_PASSWORD);
    const res = await page.request.post(`/api/visits/${visitId}/archive`, { data: {} });
    const body = await res.text();

    // ⚠️ THIS IS THE HALF THAT CANNOT BE SKIPPED. A predicate matching NOTHING
    // would satisfy the refusal test above perfectly — `updateMany` would return
    // { count: 0 }, the route would report success, and the archive would
    // silently not happen. Only asserting that the RIGHT caller's write LANDS
    // tells a correct predicate from a broken one.
    expect(res.status(), `the owning practice could not archive its own visit: ${body}`).toBe(200);

    const archived = sql(`SELECT COALESCE("archivedAt"::text,'-') FROM transcribe_visits WHERE id='${visitId}';`);
    expect(
      archived,
      'the route reported success but the row was never written — this is exactly ' +
        'the count-0 no-op that a refusal-only proof cannot see',
    ).not.toBe('-');
  });

  test('⚠️ THE HELPER REFUSES A NO-OP rather than reporting success', () => {
    // `scopedUpdate` throws when count === 0, restoring the error signal that
    // `update` gave and `updateMany` does not. Asserted at the unit level here
    // rather than by contriving a race: the property is about the helper, and a
    // race would make the test flaky in exchange for no extra information.
    const src = execSync('cat src/lib/practice-scope.ts', { encoding: 'utf8' });
    expect(src).toMatch(/if \(res\.count === 0\) throw new ScopedWriteMissError/);

    // ⚠️ THIS ASSERTED `where: unknown` AND BROKE ON A STRICTLY BETTER SIGNATURE.
    // F-TYPE made `scopedUpdate` GENERIC — `where: TWhere` — because `unknown`
    // is the TOP type and therefore CONTRAVARIANT in that position, so once the
    // shared Prisma client was typed no real delegate was assignable to it. The
    // generic version still takes the predicate as a parameter; it additionally
    // type-checks it. The guard failed a change that improved exactly the
    // property it exists to protect.
    //
    // The lesson is the house one: **assert the PROPERTY, not the spelling.**
    // The property is "the CALLER supplies the predicate" — because
    // note_templates scope through `doctorId` and the other two through a
    // column, so a helper that built its own would be wrong for one of them.
    // Both directions are checked, because the positive alone would pass on a
    // helper that took a predicate AND then ignored it.
    expect(
      src,
      'scopedUpdate must TAKE the predicate — the caller knows whether this ' +
        'model scopes through a column or through doctorId',
    ).toMatch(/export async function scopedUpdate[\s\S]{0,400}\n\s+where: \w+,/);
    expect(
      src.slice(src.indexOf('export async function scopedUpdate')),
      'scopedUpdate must NOT construct a practice predicate of its own — that ' +
        'is the caller\'s decision and getting it wrong is silent',
    ).not.toMatch(/scopedUpdate[\s\S]{0,600}practiceId:\s*\w/);
  });
});
