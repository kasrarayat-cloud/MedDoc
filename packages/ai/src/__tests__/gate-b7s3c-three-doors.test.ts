// ============================================================================
// B7 STEP 3c — THE THREE DOORS, AND THE ONE KEY THAT MAKES THEM SAFE.
// ----------------------------------------------------------------------------
// Ruling #99 authorized a promo grant reachable through three doors — signup,
// backfill, reactivation — and ruling #100 turned one of its clauses into an
// obligation on THIS file:
//
//   "if the occasion-free per-practice idempotency key makes a second grant
//    unrepresentable across ALL THREE doors, the global unique IS the
//    constraint, and the ledger records that WITH THE KEY-DERIVATION CITED.
//    Otherwise add the CHECK."
//
// So this gate is the verification that discharges the choice. It is not a
// preference and it is not a description: each arm below is a thing that would
// be FALSE if the key were wrong.
//
// ⚠️ WHY A SOURCE-LEVEL GATE AND NOT ONLY A BEHAVIOURAL ONE. Two of the three
// doors cannot be exercised by a unit test — one is a Next server action inside
// a signup transaction, the other lives in `apps/meddoc-pro`, which is
// DECOMMISSIONED and is not typechecked or built by CI at all. A behavioural
// test would therefore cover door 2 and silently claim the set. AGENTS.md's
// shared-component rule prescribes exactly this fallback: where the behaviour
// cannot live on the component, "make the missing case fail a test rather than
// render quietly". The census below is that test, and it is the ONLY thing in
// CI that reads meddoc-pro's source.
// ============================================================================

import { readFileSync } from 'node:fs';

import { describe, it, expect } from 'vitest';

import { PROMO_GRANT_MICRO_USD, promoGrantKey } from '../billing-grant';

const REPO = '../..';

const SIGNUP_DOOR = `${REPO}/apps/transcribe-md/src/actions/auth.ts`;
const BACKFILL_DOOR = `${REPO}/apps/transcribe-md/scripts/backfill-promo-grants.ts`;
const REACTIVATION_DOOR = `${REPO}/apps/meddoc-pro/src/app/system-admin/actions.ts`;
const SCHEMA = `${REPO}/packages/db/prisma/schema.prisma`;

const read = (p: string) => readFileSync(p, 'utf8');

/** Strip `//` and `/* *\/` comments. The prose in this repo NAMES the symbols
 *  under test — this file's own header does — and AGENTS.md is five sightings
 *  deep into the substring family precisely because comments are where the
 *  words you are grepping for are guaranteed to appear. */
function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
}

describe('B7 step 3c — the idempotency key is occasion-free', () => {
  it('is a pure function of the practice id — same input, same key, forever', () => {
    // ⚠️ THIS IS THE LOAD-BEARING ARM. If the key carried a date, a run id, an
    // attempt number or anything random, a second grant would be a DIFFERENT
    // ROW rather than a refused one — and the global unique would be enforcing
    // nothing. Every other claim in ruling #100's verification rests on this.
    const a = promoGrantKey('practice_abc');
    const b = promoGrantKey('practice_abc');
    expect(a).toBe(b);

    // Distinct practices must not collide, or one practice's grant would refuse
    // another's.
    expect(promoGrantKey('practice_abc')).not.toBe(promoGrantKey('practice_abd'));

    // And the derivation is CITED, not merely asserted — ruling #100 requires
    // the ledger to record it. This is the string the ledger row quotes.
    expect(a).toBe('grant:promo:practice:practice_abc');
  });

  it('the key contains NOTHING that varies between two runs', () => {
    // A stricter statement of the arm above, and the one that catches a future
    // edit rather than today's code: the key may contain the practice id and
    // fixed vocabulary, and nothing else. A digit that is not part of the
    // practice id would be a date or a counter.
    const key = promoGrantKey('PRACTICEID');
    const withoutTheId = key.replace('PRACTICEID', '');
    expect(withoutTheId).toBe('grant:promo:practice:');
    expect(/\d/.test(withoutTheId), 'the key carries a number the practice id did not supply').toBe(
      false,
    );
  });

  it('`idempotencyKey` is GLOBALLY unique in the schema — so the key IS the constraint', () => {
    // The key being occasion-free is only half. It is the DATABASE's global
    // unique that makes a second grant unrepresentable rather than merely
    // discouraged — and that is what lets step 3c ship without an extra CHECK.
    const schema = read(SCHEMA);
    expect(schema).toMatch(/idempotencyKey\s+String\?\s+@unique/);
  });

  it('POSITIVE CONTROL — the schema matcher can fail', () => {
    // Without this, a typo'd regex would pass the arm above forever and read
    // exactly like a clean run.
    const schema = read(SCHEMA);
    expect(/thisFieldDoesNotExist\s+String\?\s+@unique/.test(schema)).toBe(false);
  });

  it('the grant amount is the ruled constant, in integer micro-dollars', () => {
    expect(PROMO_GRANT_MICRO_USD).toBe(10_000_000n);
    expect(typeof PROMO_GRANT_MICRO_USD).toBe('bigint');
  });
});

describe('B7 step 3c — the door census', () => {
  const doors = [
    { name: 'signup', path: SIGNUP_DOOR },
    { name: 'backfill', path: BACKFILL_DOOR },
    { name: 'reactivation', path: REACTIVATION_DOOR },
  ];

  it('all three doors exist and call the ONE writer', () => {
    for (const d of doors) {
      const src = stripComments(read(d.path));
      expect(src, `${d.name} door does not call grantPromoCredit`).toMatch(/grantPromoCredit\s*\(/);
    }
  });

  it('POSITIVE CONTROL — the census reads real files with real content', () => {
    // The emptiness defect: a path typo would make `stripComments(read(...))`
    // throw, but a matcher applied to a file that merely lacks the symbol would
    // pass a `.not.toMatch`. Every arm here is quantified over these files, so
    // prove they are non-trivial first.
    for (const d of doors) {
      expect(read(d.path).length, `${d.name} door file is empty`).toBeGreaterThan(500);
    }
    // …and that the matcher itself discriminates.
    expect(/grantPromoCredit\s*\(/.test('nothing here')).toBe(false);
  });

  it('every door that grants also AUDITS it — ruling #99, one audit row per grant', () => {
    // ⚠️ THE PAIRING IS THE POINT. `logAudit` is fire-and-forget by design, so a
    // door that granted and forgot to audit would work perfectly and leave no
    // record. Nothing at runtime would ever say so.
    for (const d of doors) {
      const src = stripComments(read(d.path));
      expect(src, `${d.name} door grants without writing PROMO_GRANT_CREDITED`).toMatch(
        /PROMO_GRANT_CREDITED/,
      );
    }
  });

  it('no door invents its own key or its own amount', () => {
    // A second key derivation would defeat the global unique — two doors could
    // then each write "the" grant. A hardcoded amount would let the doors drift
    // apart, which is exactly why `PROMO_GRANT_MICRO_USD` is a constant and not
    // a parameter.
    for (const d of doors) {
      const src = stripComments(read(d.path));
      expect(src, `${d.name} door builds its own idempotency key`).not.toMatch(
        /['"`]grant:promo:practice:/,
      );
      expect(src, `${d.name} door hardcodes a grant amount`).not.toMatch(/10_000_000n|10000000n/);
    }
  });

  it('THE REACTIVATION PREDICATE — every user-write that sets isActive:true grants', () => {
    // ⚠️ SWEPT BY PREDICATE, NEVER BY ORM VERB. T6's CHECK sweep is the
    // precedent and the warning: 24 user write sites, 15 of them `update`, and
    // a `create`-shaped sweep sees none of them. The predicate here is "a
    // practice with an active member has a promo grant", and the write that can
    // falsify it is the one that makes a member active again.
    //
    // This arm is deliberately narrow — it asserts the ONE known reactivation
    // site still grants. Its value is as a TRIPWIRE: if somebody adds a second
    // reactivation path, or moves this one into the live app, the census above
    // is what has to be updated, and this failing is how they find out.
    const src = stripComments(read(REACTIVATION_DOOR));
    const reactivationWrites = [...src.matchAll(/isActive:\s*true/g)];
    expect(
      reactivationWrites.length,
      'the reactivation site no longer sets isActive:true — the door moved, and ' +
        'the grant must move with it',
    ).toBeGreaterThan(0);
    expect(src).toMatch(/grantPromoCredit\s*\(/);
  });

  it('THE SIGNUP GRANT IS GUARDED BY `!membership` — a collision inside that transaction is fatal', () => {
    // ⚠️ THIS ARM EXISTS BECAUSE THE FIRST DRAFT OMITTED THE GUARD AND WOULD
    // HAVE SILENTLY DESTROYED SIGNUPS. Granting on the invite branch can
    // collide with the practice's existing grant; a unique violation aborts the
    // WHOLE Postgres transaction; and `COMMIT` on an aborted transaction is
    // converted to `ROLLBACK` with no error raised. Measured on QA 2026-08-12.
    //
    // So the invited doctor's account would silently not exist. Nothing in the
    // unit suite could see it — a mocked client cannot abort — which is why the
    // guard is pinned HERE, at the source, rather than trusted to a test that
    // stubs the very failure mode in question.
    const src = stripComments(read(SIGNUP_DOOR));
    expect(
      src,
      'the signup grant is no longer guarded by !membership — an invite into an ' +
        'already-funded practice will collide, poison the transaction, and roll ' +
        'the account back silently',
    ).toMatch(/if\s*\(\s*!membership\s*\)\s*\{[\s\S]{0,400}?grantPromoCredit\(/);
  });

  it('the backfill PRE-FILTERS rather than absorbing collisions in its transaction', () => {
    // Same defect, same transaction semantics, the other door. The backfill
    // must read which keys exist and insert only the rest; relying on
    // `already_granted` dies on the first funded practice and makes every
    // re-run fail — the opposite of the idempotency ruling #99 required.
    const src = stripComments(read(BACKFILL_DOOR));
    expect(src, 'the backfill no longer pre-filters already-funded practices').toMatch(
      /findMany\([\s\S]{0,200}idempotencyKey/,
    );
    expect(src, 'the backfill must not treat a collision as a tidy skip').toMatch(/GUARD 8 ABORT/);
  });

  it('the signup door grants INSIDE the transaction and audits OUTSIDE it', () => {
    // Ordering, not presence. A grant outside the transaction can leave a
    // practice that exists and is unfunded; an audit inside it can record a
    // grant that a later statement rolled back. Both are silent.
    //
    // ⚠️ THE BOUNDARY IS THE TRANSACTION'S **END**, NOT THE GRANT CALL — AND
    // THE FIRST VERSION OF THIS ARM GOT THAT WRONG. It compared the audit's
    // position against `grantPromoCredit(...)` and therefore passed for BOTH
    // the correct code and a mutation that moved the audit inside the closure,
    // two lines below the grant. That is the defect AGENTS.md names as "a check
    // whose TITLE is narrower than what it MEASURES": the assertion was correct
    // about a quantity nobody wanted. Caught by mutation M3, which is the only
    // thing that could have caught it.
    //
    // `'[signup] create failed:'` sits in the `catch` attached to the
    // transaction, so it is unambiguously PAST the closure's end.
    const src = read(SIGNUP_DOOR);
    const txStart = src.indexOf('prisma.$transaction');
    const txEnd = src.indexOf("console.error('[signup] create failed:");
    const grantAt = src.indexOf('grantPromoCredit(practice.id, tx)');
    const auditAt = src.indexOf("action: 'PROMO_GRANT_CREDITED'");

    expect(txStart, 'signup transaction not found').toBeGreaterThan(-1);
    expect(
      txEnd,
      "the transaction's catch marker moved — this arm can no longer locate the " +
        'closure boundary and must be re-anchored, not deleted',
    ).toBeGreaterThan(-1);
    expect(grantAt, 'grant call not found').toBeGreaterThan(-1);
    expect(auditAt, 'audit call not found').toBeGreaterThan(-1);

    // The boundary marker must really sit between the two, or the arm is
    // vacuous in the other direction.
    expect(txEnd, 'the boundary marker precedes the transaction').toBeGreaterThan(txStart);

    expect(grantAt, 'the grant is not inside the signup transaction').toBeGreaterThan(txStart);
    expect(grantAt, 'the grant is outside the transaction — an unfunded practice can commit')
      .toBeLessThan(txEnd);
    expect(
      auditAt,
      'the audit row is written INSIDE the transaction — it would record a grant ' +
        'that a rollback then discards',
    ).toBeGreaterThan(txEnd);

    // The grant passes the transaction client; the audit does not take one.
    expect(src).toMatch(/grantPromoCredit\(practice\.id,\s*tx\)/);
  });
});

describe('B7 step 3c — the backfill refuses by default', () => {
  const src = stripComments(read(BACKFILL_DOOR));

  it('requires --target and --expect, and neither has a default', () => {
    expect(src).toMatch(/--target=qa\|prod is REQUIRED/);
    expect(src).toMatch(/--expect=<N> is REQUIRED/);
  });

  it('writes only under --commit; the default path rolls back', () => {
    expect(src).toMatch(/argv\.includes\('--commit'\)/);
    expect(src, 'the dry run must roll back a REAL transaction, not skip the writes').toMatch(
      /throw ROLLBACK/,
    );
  });

  it('re-derives the population instead of reading it from a list', () => {
    // Ruling #99: "population re-derived at execution time, never copied from
    // this text". A literal 175 anywhere in the executable body would be that
    // copy.
    expect(src).toMatch(/derivePopulation/);
    expect(src, 'the backfill hardcodes a population size').not.toMatch(/\b175\b/);
  });
});
