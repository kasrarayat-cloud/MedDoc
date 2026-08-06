// ============================================================================
// T6 — the sign gate, proven by ATTEMPT in all three directions.
// ----------------------------------------------------------------------------
// SPEC §4.1a: "OWNER and CLINICIAN may sign any UNSIGNED visit in that practice,
// regardless of who created it. TECH is refused by name, server-side,
// fail-closed. Not hidden in the UI — refused by the route, so a scripted caller
// is refused identically."
//
// So this file makes SCRIPTED requests. A UI walk would prove the button is
// hidden, which is not the claim: R1's lesson is that a gate nothing enforces is
// one path away from not existing.
//
// ⚠️ THREE DIRECTIONS, AND EACH KILLS A DIFFERENT WRONG IMPLEMENTATION.
//
//   POSITIVE   CLINICIAN signs a colleague's unsigned visit → the visit signs,
//              and `signedBy` ≠ `createdBy`.
//              Kills: a gate that refuses everyone but the author. This is also
//              T4's positive gate, which has been blocked since 2026-08-06 for
//              want of exactly this fixture.
//
//   NEGATIVE   TECH attempts the same visit → 403, and the body NAMES the role
//              reason rather than 404-ing.
//              Kills: hiding the button; and kills a 404, which would be the
//              easy implementation and the wrong one — §4.1a says a clinician
//              deserves the true fact, and there is no enumeration risk because
//              §4.1b already lets a TECH SEE the visit.
//
//   UNCHANGED  a member of ANOTHER practice → 404, silent.
//              Kills: a role check that replaced the tenancy check instead of
//              layering on it. Without this, "TECH is refused" could be true
//              while the practice wall had quietly become a role wall.
//
// ⚠️ AND THE SIGNED STATE IS ROLLED BACK. The positive case really signs a
// visit, which is a one-way transition guarded by a CHECK constraint. It runs
// inside its own visit and the row is reset in `afterAll` — the attempt has to
// be consequential enough to be real and never consequential beyond this file.
// ============================================================================

import { execSync } from 'node:child_process';

import { expect, test } from '@playwright/test';

import { QA_COMPOSE as COMPOSE, QA_DB as DB } from '../helpers/qa-compose';
import { loginUser } from '../helpers/auth';

const ALPHA_1 = 't1-alpha-1@t1.invalid'; // OWNER, author of the visits
const ALPHA_2 = 't1-alpha-2@t1.invalid'; // CLINICIAN — may sign a colleague's
const ALPHA_3 = 't1-alpha-3@t1.invalid'; // TECH — may not sign, may see
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

/** An UNSIGNED visit authored by alpha-1 — the one a colleague will sign. */
function unsignedAlphaVisit(): string {
  return sql(`
    SELECT v.id FROM transcribe_visits v
    JOIN users u ON u.id = v."userId"
    WHERE u.email = '${ALPHA_1}'
      AND v."signedAt" IS NULL
      AND v."deletedAt" IS NULL AND v."archivedAt" IS NULL
    ORDER BY v."createdAt" DESC LIMIT 1;
  `);
}

const TOUCHED: string[] = [];

test.describe('T6 — who may sign, proven by attempt', () => {
  test.beforeAll(() => {
    expect(
      MEMBER_PASSWORD.length,
      'T1_MEMBER_PASSWORD is unset — this pack cannot log the fixture members in',
    ).toBeGreaterThan(0);

    // ⚠️ NON-VACUITY. If the roles are not what this file assumes, every
    // assertion below tests a different member than its name claims — and the
    // negative case would pass for the wrong reason (a CLINICIAN refused for
    // some other cause reads exactly like a TECH refused correctly).
    const roles = sql(`
      SELECT string_agg(email || '=' || COALESCE("practiceRole"::text,'null'), ' ' ORDER BY email)
      FROM users WHERE email IN ('${ALPHA_1}','${ALPHA_2}','${ALPHA_3}');`);
    expect(roles, 'the T1 fixture does not carry the three roles this pack needs').toBe(
      `${ALPHA_1}=OWNER ${ALPHA_2}=CLINICIAN ${ALPHA_3}=TECH`,
    );
    expect(unsignedAlphaVisit().length, 'no UNSIGNED alpha visit to sign').toBeGreaterThan(0);
  });

  test.afterAll(() => {
    // Reset anything this file signed. A signed visit is a one-way transition in
    // the product; it is not one in a synthetic fixture, and leaving it signed
    // would silently shrink the pool the next run draws from.
    for (const id of TOUCHED) {
      sql(`UPDATE transcribe_visits
             SET "signedAt" = NULL, "signedBy" = NULL, status = 'READY'
           WHERE id = '${id}';`);
    }
  });

  test('⚠️ POSITIVE — a CLINICIAN signs a COLLEAGUE\'s visit, and signedBy ≠ createdBy', async ({
    page,
  }) => {
    const visitId = unsignedAlphaVisit();
    TOUCHED.push(visitId);
    await loginUser(page, ALPHA_2, MEMBER_PASSWORD);

    const res = await page.request.post(`/api/visits/${visitId}/sign`, {
      data: { attestation: { acknowledged: true }, destinations: [] },
    });

    // ⚠️ NOT an assertion on 200 alone. The gates this route enforces
    // (attestation, Rx overrides, E/M confirmation) are identity-independent by
    // §4.1a and may legitimately refuse for their own reasons — but NEVER for a
    // role reason. That is the claim being tested.
    const body = await res.text();

    // ⚠️ ASSERT 200, NOT MERELY "not 403" — AND THIS IS SCAR TISSUE.
    // The first version asserted only `not 403` and `not ROLE_MAY_NOT_SIGN`, so
    // it PASSED on a 400 ("invalid destinations payload") from a malformed body
    // — the sign never happened and the signedBy comparison below was skipped
    // by its own `if`. A positive gate that passes when nothing was signed is
    // the vacuity this programme keeps meeting.
    expect(res.status(), `a CLINICIAN could not sign a colleague's visit: ${body}`).toBe(200);
    expect(body).not.toContain('ROLE_MAY_NOT_SIGN');

    {
      const row = sql(`SELECT COALESCE("signedBy",'-') || '|' || COALESCE("createdBy",'-')
                       FROM transcribe_visits WHERE id = '${visitId}';`);
      const [signedBy, createdBy] = row.split('|');
      expect(signedBy, 'the visit signed but recorded no signer').not.toBe('-');
      // ⚠️ THIS IS T4'S POSITIVE GATE, and it is the whole reason the fixture
      // needed a second member. Production has 16 signed visits and signer ==
      // author in every one — not evidence the attribution works, evidence the
      // data has never exercised it.
      expect(
        signedBy,
        'signedBy equals createdBy — a solo-practice run cannot prove attribution',
      ).not.toBe(createdBy);
    }
  });

  test('⚠️ NEGATIVE — a TECH is REFUSED BY NAME, not 404ed', async ({ page }) => {
    const visitId = unsignedAlphaVisit();
    await loginUser(page, ALPHA_3, MEMBER_PASSWORD);

    const res = await page.request.post(`/api/visits/${visitId}/sign`, {
      data: { attestation: { acknowledged: true }, destinations: [] },
    });
    const body = await res.text();

    expect(res.status(), `TECH was not refused with 403. Body: ${body}`).toBe(403);
    expect(body, 'the refusal does not name the role reason').toContain('ROLE_MAY_NOT_SIGN');
    // ⚠️ AND EXPLICITLY NOT A 404. A 404 would be the easy implementation and
    // the wrong one: the TECH can already SEE this visit under §4.1b, so
    // pretending it does not exist is a lie that costs a clinician time.
    expect(res.status(), 'TECH got a 404 — "you may not sign" told as "no such visit"').not.toBe(
      404,
    );

    // The refusal is AUDITED. A gate nothing records is one path away from not
    // existing (R1).
    const audited = sql(`
      SELECT count(*) FROM audit_logs
      WHERE action::text = 'SIGN_BLOCKED_ROLE_NOT_PERMITTED'
        AND "targetId" = '${visitId}';`);
    expect(Number(audited), 'the role refusal wrote no audit row').toBeGreaterThan(0);
  });

  test('⚠️ UNCHANGED — another practice still gets a silent 404', async ({ page }) => {
    const visitId = unsignedAlphaVisit();
    await loginUser(page, BETA_1, MEMBER_PASSWORD);

    const res = await page.request.post(`/api/visits/${visitId}/sign`, {
      data: { attestation: { acknowledged: true }, destinations: [] },
    });
    const body = await res.text();

    expect(res.status(), `cross-practice sign was not 404. Body: ${body}`).toBe(404);
    // ⚠️ AND THE BODY MUST NOT NAME A ROLE. Leaking "your role may not sign"
    // here would confirm the visit exists to someone in another practice —
    // turning the role message into the enumeration oracle the 404 prevents.
    expect(body, 'a cross-practice refusal leaked a role reason').not.toContain(
      'ROLE_MAY_NOT_SIGN',
    );
  });
});
