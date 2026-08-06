// ============================================================================
// T4-a — attribution: a signature without a signer is unrepresentable.
// ----------------------------------------------------------------------------
// ⚠️ THIS IS THE NEGATIVE HALF OF T4'S GATE, AND IT SAYS SO.
// T4's gate has two directions:
//   NEGATIVE — the forbidden state is refused by name.            ← this file
//   POSITIVE — a non-owner member signs and signedBy ≠ createdBy. ← T4-b
//
// The positive half needs T1's second member to authenticate and drive the real
// sign route. Simulating it with a direct UPDATE would prove the columns CAN
// differ and say nothing about whether the ROUTE stamps the right person, which
// is the only thing worth asserting. So it waits for T4-b rather than being
// approximated here. T4 is PARTIAL until then, and the ledger says so.
//
// ⚠️ A SOLO-PRACTICE DATABASE CANNOT TELL THESE COLUMNS APART. All 16 signed
// visits in production today have signer == author. That is not evidence the
// attribution works; it is evidence the data has never exercised it.
// ============================================================================

import { execSync } from 'node:child_process';

import { expect, test } from '@playwright/test';

import { QA_COMPOSE as COMPOSE, QA_DB as DB } from '../helpers/qa-compose';

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
const num = (sql: string) => Number.parseInt(trySql(sql).out.trim(), 10);

test.describe('T4-a — attribution columns', () => {
  test('the columns exist with the right nullability', () => {
    const created = trySql(
      `SELECT is_nullable FROM information_schema.columns WHERE table_name='transcribe_visits' AND column_name='createdBy';`,
    ).out.trim();
    const signed = trySql(
      `SELECT is_nullable FROM information_schema.columns WHERE table_name='transcribe_visits' AND column_name='signedBy';`,
    ).out.trim();
    expect(created, 'createdBy must be NOT NULL — every visit has an author').toBe('NO');
    // ⚠️ signedBy is NULLABLE ON PURPOSE. An unsigned visit has no signer, and a
    // sentinel would be a lie about attestation. The CHECK below is what stops
    // that nullability from covering a real signature.
    expect(signed, 'signedBy must stay nullable — unsigned visits have no signer').toBe('YES');
  });

  test('every visit is attributed, and every signature has a signer', () => {
    expect(num(`SELECT count(*) FROM transcribe_visits WHERE "createdBy" IS NULL;`)).toBe(0);
    expect(
      num(`SELECT count(*) FROM transcribe_visits WHERE "signedAt" IS NOT NULL AND "signedBy" IS NULL;`),
      'a signed visit has no signer',
    ).toBe(0);

    // NON-VACUITY, both ways: there are visits, and some of them are signed.
    expect(num(`SELECT count(*) FROM transcribe_visits;`), 'no visits at all').toBeGreaterThan(0);
    expect(
      num(`SELECT count(*) FROM transcribe_visits WHERE "signedAt" IS NOT NULL;`),
      'no SIGNED visits — the signer assertion above is free',
    ).toBeGreaterThan(0);
  });

  test('⚠️ THE NEGATIVE GATE — a signature without a signer is REFUSED by name', () => {
    // ⚠️ WRAPPED IN A TRANSACTION THAT ROLLS BACK, AND THE REASON IS SCAR TISSUE.
    // The first version ran this UPDATE bare. That is harmless while the CHECK
    // holds — the statement is rejected and nothing changes. But during a
    // mutation run, with the constraint temporarily DROPPED, the same UPDATE
    // SUCCEEDS: it nulled the signer on 21 signed visits, and re-adding the
    // constraint then failed silently because the rows it had just created
    // violated it. The database was left with unattributed signatures AND no
    // constraint — the exact state this test exists to prove impossible.
    //
    // ROLLBACK makes the attempt observable without being consequential.
    const r = trySql(
      `BEGIN;
       UPDATE transcribe_visits SET "signedBy" = NULL WHERE "signedAt" IS NOT NULL;
       ROLLBACK;`,
    );
    expect(
      r.ok,
      'a signed visit accepted a NULL signer — the attribution guarantee does not exist',
    ).toBe(false);
    // Refused for the RIGHT reason, not incidentally (a typo also fails).
    expect(r.out).toContain('transcribe_visits_signed_requires_signer');
  });

  test('POSITIVE CONTROL — the same UPDATE on an UNSIGNED visit succeeds', () => {
    // Without this, the refusal above could be any error at all: a bad column,
    // a permissions problem, a dead connection. This proves the constraint
    // discriminates on the signed-ness rather than rejecting every write.
    const r = trySql(
      `BEGIN;
       UPDATE transcribe_visits SET "signedBy" = NULL WHERE "signedAt" IS NULL;
       ROLLBACK;`,
    );
    expect(
      r.ok,
      'clearing signedBy on an UNSIGNED visit was also refused — the constraint ' +
        'is broader than it claims, or this UPDATE is simply broken',
    ).toBe(true);
  });
});
