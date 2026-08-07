// ============================================================================
// T8 — an invite mints a MEMBER, not just a user. Proven by attempt, every way.
// ----------------------------------------------------------------------------
// SPEC §1.3: "An invite code today mints a user; after this it mints a *member
// of a named practice with a named role*."
//
// ⚠️ FOUR DIRECTIONS, AND EACH KILLS A DIFFERENT WRONG IMPLEMENTATION.
//
//   CARRIES     an invite with practice+role admits with EXACTLY that role into
//               EXACTLY that practice.
//               Kills: reading the practice and ignoring the role — which would
//               make every invited CLINICIAN an OWNER of the clinic they
//               joined, and would be INVISIBLE because the account works.
//
//   LEGACY      a role-less invite mints a fresh solo practice, OWNER.
//               Kills: a branch that treats NULL as an error or as a default
//               practice. Every invite issued before T8 is in this state, and
//               the migration header declares this as their contract.
//
//   CONSUMED    a spent code is refused.
//   FOREIGN     an unknown code is refused.
//               Kill: a T8 branch that reaches the membership lookup BEFORE the
//               validity checks — which would leak whether a practice exists to
//               anyone probing codes.
//
// ⚠️ EVERY ACCOUNT THIS FILE CREATES IS DELETED IN afterAll. A signup writes a
// user, a practice and audit rows; leaving them behind would grow the fixture
// every run and eventually change what other packs measure.
// ============================================================================

import { execSync } from 'node:child_process';
import { createHash } from 'node:crypto';

import { expect, test } from '@playwright/test';

import { QA_COMPOSE as COMPOSE, QA_DB as DB } from '../helpers/qa-compose';
import { TEST_PASSWORD } from '../helpers/test-utils';

function sql(query: string): string {
  return String(
    execSync(`${COMPOSE} exec -T postgres psql -U meddoc -d ${DB} -v ON_ERROR_STOP=1 -A -t -f -`, {
      input: query,
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
    }),
  ).trim();
}

/** The app hashes invite codes with sha256 before lookup — mirror it exactly. */
const hash = (raw: string) => createHash('sha256').update(raw.trim().toUpperCase()).digest('hex');

const CARRIES = 'T8-CARRIES-ROLE';
const LEGACY = 'T8-LEGACY-NOROLE';
const CONSUMED = 'T8-ALREADY-SPENT';
const CREATED: string[] = [];

function mkEmail(tag: string): string {
  return `t8-${tag}-${Date.now().toString(36)}@t8.invalid`;
}

async function signup(page: import('@playwright/test').Page, code: string, email: string) {
  await page.goto('/signup');
  await page.getByLabel('Invite code').fill(code);
  await page.getByLabel('Full name').fill('T8 Invitee');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD);
  await page.getByLabel('Confirm password').fill(TEST_PASSWORD);
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: /create account/i }).click();
}

test.describe('T8 — the invite carries practice + role', () => {
  test.beforeAll(() => {
    const alpha = sql(`SELECT id FROM practices WHERE slug = 't1-alpha';`);
    expect(alpha.length, 'the T1 alpha practice is missing — seed did not run').toBeGreaterThan(0);

    sql(`DELETE FROM invite_codes WHERE "codeHash" IN
           ('${hash(CARRIES)}','${hash(LEGACY)}','${hash(CONSUMED)}');`);

    // CARRIES — practice + role together (the CHECK refuses them apart).
    sql(`INSERT INTO invite_codes (id,"codeHash",label,"maxUses","usedCount","createdAt","updatedAt","practiceId","practiceRole")
         VALUES ('t8-carries','${hash(CARRIES)}','T8 carries',1,0,now(),now(),'${alpha}','CLINICIAN');`);
    // LEGACY — the pre-T8 shape: no practice, no role.
    sql(`INSERT INTO invite_codes (id,"codeHash",label,"maxUses","usedCount","createdAt","updatedAt")
         VALUES ('t8-legacy','${hash(LEGACY)}','T8 legacy',1,0,now(),now());`);
    // CONSUMED — already spent.
    sql(`INSERT INTO invite_codes (id,"codeHash",label,"maxUses","usedCount","createdAt","updatedAt","practiceId","practiceRole")
         VALUES ('t8-spent','${hash(CONSUMED)}','T8 spent',1,1,now(),now(),'${alpha}','TECH');`);
  });

  test.afterAll(() => {
    for (const email of CREATED) {
      // Order matters: audit rows reference the user, and the practice is
      // referenced BY the user.
      sql(`DELETE FROM audit_logs WHERE "userId" IN (SELECT id FROM users WHERE email='${email}');`);
      sql(`DELETE FROM users WHERE email='${email}';`);
    }
    sql(`DELETE FROM practices WHERE name = 'Solo — T8 Invitee';`);
    sql(`DELETE FROM invite_codes WHERE id IN ('t8-carries','t8-legacy','t8-spent');`);
  });

  test('⚠️ CARRIES — admits with EXACTLY that role into EXACTLY that practice', async ({ page }) => {
    const email = mkEmail('carries');
    CREATED.push(email);
    await signup(page, CARRIES, email);

    // Assert on the ROW, not the redirect. A signup that lands on the home page
    // proves an account exists; it says nothing about which practice it joined
    // or with what rights — which is the entire subject of this test.
    await expect
      .poll(
        () =>
          sql(`SELECT COALESCE(u."practiceRole"::text,'-') || '|' || COALESCE(p.slug,'-')
               FROM users u LEFT JOIN practices p ON p.id = u."practiceId"
               WHERE u.email = '${email}';`),
        { timeout: 20_000, message: 'the invited account never appeared' },
      )
      .toBe('CLINICIAN|t1-alpha');

    // ⚠️ AND IT DID NOT MINT A PRACTICE. The failure this catches is a branch
    // that reads the invite's role but still creates a solo practice — the
    // account would look right in isolation and be in the wrong clinic.
    const solos = sql(`SELECT count(*) FROM practices WHERE name = 'Solo — T8 Invitee';`);
    expect(solos, 'a solo practice was minted despite the invite naming one').toBe('0');
  });

  test('⚠️ LEGACY — a role-less invite still mints a solo practice, OWNER', async ({ page }) => {
    const email = mkEmail('legacy');
    CREATED.push(email);
    await signup(page, LEGACY, email);

    await expect
      .poll(
        () =>
          sql(`SELECT COALESCE(u."practiceRole"::text,'-') || '|' || COALESCE(p.name,'-')
               FROM users u LEFT JOIN practices p ON p.id = u."practiceId"
               WHERE u.email = '${email}';`),
        { timeout: 20_000, message: 'the legacy-invite account never appeared' },
      )
      .toBe('OWNER|Solo — T8 Invitee');

    // The declared contract: NULL means legacy, not "an error to fix later".
    const joined = sql(`
      SELECT count(*) FROM users u JOIN practices p ON p.id = u."practiceId"
      WHERE u.email='${email}' AND p.slug='t1-alpha';`);
    expect(joined, 'a role-less invite admitted into a real practice').toBe('0');
  });

  test('⚠️ CONSUMED and FOREIGN are refused, and no account is created', async ({ page }) => {
    for (const [label, code] of [
      ['consumed', CONSUMED],
      ['foreign', 'T8-NO-SUCH-CODE-AT-ALL'],
    ] as const) {
      const email = mkEmail(label);
      await signup(page, code, email);

      // ⚠️ THE ROW IS THE ASSERTION. A form that shows an error while still
      // creating the account is the failure worth catching, and the message
      // alone cannot distinguish the two.
      const n = sql(`SELECT count(*) FROM users WHERE email = '${email}';`);
      expect(n, `a ${label} invite created an account`).toBe('0');
    }

    // And the spent code's counter did not move — a refusal must not consume.
    const used = sql(`SELECT "usedCount" FROM invite_codes WHERE id='t8-spent';`);
    expect(used, 'a refused signup still spent a use').toBe('1');
  });
});
