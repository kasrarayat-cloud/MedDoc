// ============================================================================
// T5 — read is PRACTICE-UNIFORM (§4.1b), proven through the APP, not the DB.
// ----------------------------------------------------------------------------
// ⚠️ WHY THIS EXISTS SEPARATELY FROM `31-practice-isolation`. That file proves
// the COLUMN isolates, by running two SQL queries and requiring their answers to
// differ. It is the right proof for T3 and it is blind to the thing T5 changed:
// whether the application's read path actually uses the column. A route that
// still filtered by `userId` would leave 31 completely green.
//
// So this drives a real browser through a real session against the T1 fixture,
// which is the only place two members of one practice exist.
//
// THE PAIR, AND WHY BOTH HALVES ARE REQUIRED
//
//   NEW       alpha-2 opens a visit authored by alpha-1 → the note renders.
//             Before T5 this was a 404: `/visits/[id]` compared `visit.userId`
//             to the session and called `notFound()`.
//   UNCHANGED beta-1 opens the SAME visit → not found.
//
// The first assertion alone would pass on a route that dropped tenancy entirely
// — which is the exact defect a widening commit is most likely to introduce, and
// it fails OPEN. The second alone would pass on the pre-T5 code. Only the pair
// distinguishes "the wall moved to the practice boundary" from "the wall is
// gone", and that distinction is the whole of §4.1b.
//
// ⚠️ AND ONE THING THAT MUST **NOT** HAVE WIDENED. The personal data export is
// author-scoped by design (§4.1b's PERSONAL_SCOPE): its subject is the USER, so
// a colleague's patients appearing there is a leak in the opposite direction —
// the one a practice-uniform migration is most likely to cause by being
// thorough. Asserted here rather than assumed.
// ============================================================================

import { execSync } from 'node:child_process';

import { expect, test } from '@playwright/test';

import { QA_COMPOSE as COMPOSE, QA_DB as DB } from '../helpers/qa-compose';
import { loginUser } from '../helpers/auth';

const ALPHA_1 = 't1-alpha-1@t1.invalid';
const ALPHA_2 = 't1-alpha-2@t1.invalid';
const BETA_1 = 't1-beta-1@t1.invalid';

// Set by the workflow step that seeds the fixture. Never defaulted: a wrong
// password would fail as "login timed out", which reads like a flake and would
// send the next person looking at the browser instead of the fixture.
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

/** A visit authored by alpha-1 — the one alpha-2 has no ownership claim on. */
function alphaOneVisit(): { id: string; practiceId: string } {
  const row = sql(`
    SELECT v.id || '|' || v."practiceId"
    FROM transcribe_visits v
    JOIN users u ON u.id = v."userId"
    WHERE u.email = '${ALPHA_1}' AND v."deletedAt" IS NULL AND v."archivedAt" IS NULL
    ORDER BY v."createdAt" DESC
    LIMIT 1;
  `);
  const [id, practiceId] = row.split('|');
  return { id, practiceId };
}

test.describe('T5 — a practice member reads the practice, and nobody else does', () => {
  test.beforeAll(() => {
    expect(
      MEMBER_PASSWORD.length,
      'T1_MEMBER_PASSWORD is unset — this pack cannot log the fixture members in',
    ).toBeGreaterThan(0);

    // ⚠️ NON-VACUITY, AND IT IS NOT OPTIONAL HERE. Every assertion below is about
    // what a page does with a visit id. If the fixture is missing, `alphaOneVisit`
    // returns an empty id, `/visits/` 404s for everyone, and the "beta is
    // refused" half passes for the wrong reason while the "alpha-2 can read"
    // half fails as a UI bug. Establish the set before asking questions of it.
    const alphaVisits = Number(
      sql(`SELECT count(*) FROM transcribe_visits v JOIN users u ON u.id = v."userId"
           WHERE u.email = '${ALPHA_1}';`),
    );
    const members = Number(
      sql(`SELECT count(*) FROM users WHERE email IN ('${ALPHA_1}', '${ALPHA_2}', '${BETA_1}');`),
    );
    expect(alphaVisits, 'the T1 fixture has no alpha-1 visits — seed did not run').toBeGreaterThan(
      0,
    );
    expect(members, 'the three T1 fixture members are not all present').toBe(3);

    // And the two alphas really are one practice while beta is another —
    // otherwise this file is testing two unrelated accounts.
    const distinct = sql(`
      SELECT count(DISTINCT "practiceId") FROM users
      WHERE email IN ('${ALPHA_1}', '${ALPHA_2}');`);
    expect(distinct, 'alpha-1 and alpha-2 are not in the same practice').toBe('1');
    const cross = sql(`
      SELECT count(*) FROM users a, users b
      WHERE a.email = '${ALPHA_1}' AND b.email = '${BETA_1}'
        AND a."practiceId" = b."practiceId";`);
    expect(cross, 'beta-1 shares alpha-1 practice — the refusal below is meaningless').toBe('0');
  });

  test('⚠️ NEW — a colleague in the same practice opens the visit', async ({ page }) => {
    const visit = alphaOneVisit();
    await loginUser(page, ALPHA_2, MEMBER_PASSWORD);
    await page.goto(`/visits/${visit.id}`);

    // ⚠️ ASSERT ON A NODE THE NOT-FOUND PAGE CANNOT RENDER. "the URL did not
    // redirect" is not evidence — Next renders notFound() in place, at the same
    // URL, with a 200-shaped client navigation. The patient name comes from the
    // visit row itself, so it exists only if the query returned it.
    const patientName = sql(
      `SELECT COALESCE(p.name, v."patientName") FROM transcribe_visits v
       LEFT JOIN transcribe_md_patients p ON p.id = v."patientId"
       WHERE v.id = '${visit.id}';`,
    );
    expect(patientName.length, 'the fixture visit has no patient name to assert on').toBeGreaterThan(
      0,
    );
    await expect(
      page.getByText(patientName, { exact: false }).first(),
      "alpha-2 got a not-found for a colleague's visit — the read did NOT widen " +
        'to the practice, or the page still compares visit.userId to the session',
      // Generous: this page runs the E/M pre-warm before it renders.
    ).toBeVisible({ timeout: 30_000 });
  });

  test('⚠️ UNCHANGED — a member of ANOTHER practice is refused the same visit', async ({
    page,
  }) => {
    const visit = alphaOneVisit();
    await loginUser(page, BETA_1, MEMBER_PASSWORD);
    await page.goto(`/visits/${visit.id}`);

    // Next's notFound() boundary. Asserting the ABSENCE of the note would pass
    // on a page that failed to render for any reason at all, so this names the
    // not-found surface positively.
    await expect(
      page.getByText(/not found|404|does not exist/i).first(),
      'beta-1 was NOT refused a visit from another practice — the practice ' +
        'predicate is missing from this route, and the widening went too far',
    ).toBeVisible({ timeout: 30_000 });
  });

  test('⚠️ NOT WIDENED — the personal data export stays author-scoped', async ({ page }) => {
    // The opposite-direction leak. `/api/settings/export-data` answers "give me
    // MY data": its subject is the user, so a practice predicate there would put
    // a colleague's patients inside somebody's personal export. Declared in the
    // guard as PERSONAL_SCOPE; asserted here so the declaration is not the only
    // thing holding it.
    await loginUser(page, ALPHA_2, MEMBER_PASSWORD);

    const own = Number(
      sql(`SELECT count(*) FROM transcribe_visits v JOIN users u ON u.id = v."userId"
           WHERE u.email = '${ALPHA_2}';`),
    );
    const practiceWide = Number(
      sql(`SELECT count(*) FROM transcribe_visits v
           WHERE v."practiceId" = (SELECT "practiceId" FROM users WHERE email = '${ALPHA_2}');`),
    );
    // Without this the assertion below is free: if alpha-2 authored every visit
    // in the practice, author-scoped and practice-scoped return the same set and
    // the test cannot tell them apart.
    expect(
      practiceWide,
      'alpha-2 authored every visit in the practice — this test cannot ' +
        'distinguish author scope from practice scope on this fixture',
    ).toBeGreaterThan(own);

    const res = await page.request.get('/api/settings/export-data');
    expect(res.status(), 'the export route did not answer').toBe(200);
    const body = await res.text();

    // Every visit id in the practice that alpha-2 did NOT author must be absent.
    const foreign = sql(`
      SELECT string_agg(v.id, ' ') FROM transcribe_visits v
      JOIN users u ON u.id = v."userId"
      WHERE v."practiceId" = (SELECT "practiceId" FROM users WHERE email = '${ALPHA_2}')
        AND u.email <> '${ALPHA_2}';`)
      .split(' ')
      .filter(Boolean);
    expect(foreign.length, 'no foreign visits to look for — see the guard above').toBeGreaterThan(0);
    const leaked = foreign.filter((id) => body.includes(id));
    expect(
      leaked,
      "a colleague's visit appeared in a PERSONAL data export — the personal " +
        'scope was widened by mistake',
    ).toEqual([]);
  });
});
