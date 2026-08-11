// ============================================================================
// GATE — B7. WHAT A STRIPE CHECKOUT EVENT MAY CREDIT, AND WHAT THE ROUTE MAY
// DO BEFORE IT HAS VERIFIED A SIGNATURE.
// ----------------------------------------------------------------------------
// RELAY B7's gate has four clauses. Three of them are statements about the
// SOURCE — an ordering, a method call, an argument — and one is about the
// decision. They are asserted separately below, because a behavioural test
// cannot see an ordering and a source scan cannot see an arithmetic.
//
//   · signature verification is the FIRST statement       → source ordering
//   · `req.text()` before anything, never `req.json()`    → source
//   · `userId`/`practiceId` passed explicitly, no session → source
//   · the credit decision itself                          → behavioural, pure
//
// ⚠️ AND ONE INVARIANT THAT IS B7's OWN, NOT THE RELAY's: NOTHING TOUCHES THE
// DATABASE BEFORE THE SIGNATURE VERIFIES. The route is unauthenticated by
// design (DISCOVERY §E.4 — the signature IS the auth), so a database write per
// unverified request is an amplification an anonymous caller controls. That is
// checked here as a source ordering too, because it is unobservable at runtime:
// a handler that wrote a row before verifying would look identical from outside.
// ============================================================================

import { readFileSync } from 'node:fs';

import { describe, it, expect } from 'vitest';

import {
  ALLOWED_METADATA_KEYS,
  centsToMicroUsd,
  decideTopup,
  topupIdempotencyKey,
  type CheckoutEventShape,
  type DbIdentity,
} from '../stripe-topup';

const ROUTE_PATH = 'src/app/api/stripe/webhook/route.ts';
const ROUTE_SRC = readFileSync(ROUTE_PATH, 'utf8');

/** The route source with `//` and `/* *\/` comments removed. EVERY source
 *  ordering below is measured on THIS, never on the raw file.
 *
 *  ⚠️ The file's header discusses `req.json()`, `prisma` and the ordering in
 *  prose, at length. Scanning the raw text would match the commentary and
 *  report whatever the comments happen to say — the substring family in
 *  AGENTS.md, four sightings deep, whose most recent member was an idempotence
 *  check satisfied by a sentence somebody had just written. */
const ROUTE_CODE = ROUTE_SRC.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');

/** A production database identity, as `describeDbTarget` yields it. */
const PROD: DbIdentity = { database: 'meddoc', host: 'postgres' };
/** The isolated QA stack's identity. */
const QA: DbIdentity = { database: 'meddoc_qa_test', host: 'postgres' };

function event(over: Partial<CheckoutEventShape> = {}, session: Record<string, unknown> = {}) {
  return {
    id: 'evt_test_1',
    type: 'checkout.session.completed',
    livemode: false,
    ...over,
    data: {
      object: {
        id: 'cs_test_1',
        amount_total: 5000,
        currency: 'usd',
        payment_status: 'paid',
        metadata: { practiceId: 'prac_1', userId: 'user_1' },
        ...session,
      },
    },
  } as CheckoutEventShape;
}

// ---------------------------------------------------------------------------
describe('B7 — the credit decision', () => {
  it('a paid USD test-mode session credits on a NON-PRODUCTION database', () => {
    const d = decideTopup(event(), QA);
    expect(d.credit).toBe(true);
    if (!d.credit) return;
    expect(d.practiceId).toBe('prac_1');
    expect(d.userId).toBe('user_1');
    // 5000 cents = $50.00 = 50_000_000 micro-dollars. Integer throughout.
    expect(d.amountMicroUsd).toBe(50_000_000n);
    expect(d.idempotencyKey).toBe('topup:stripe_session:cs_test_1');
  });

  it('a paid USD LIVE-mode session credits on PRODUCTION', () => {
    const d = decideTopup(event({ livemode: true }), PROD);
    expect(d.credit).toBe(true);
  });

  // ── THE GUARDRAIL. This is the one that matters today. ────────────────────
  it('⚠️ a TEST-mode event may NOT credit the production ledger', () => {
    const d = decideTopup(event({ livemode: false }), PROD);
    expect(d.credit).toBe(false);
    if (d.credit) return;
    expect(d.reason).toBe('mode_mismatch');
    expect(d.detail).toContain('nobody paid for it');
  });

  it('a LIVE-mode event may not credit a non-production ledger either', () => {
    const d = decideTopup(event({ livemode: true }), QA);
    expect(d.credit).toBe(false);
    if (d.credit) return;
    expect(d.reason).toBe('mode_mismatch');
  });

  it('⚠️ an UNIDENTIFIABLE database refuses in BOTH modes — the gap is deliberate', () => {
    // `staging` is confirmed by neither guard. Ruling 90(c): the two functions
    // are complements on nothing, and the set they both decline is "we cannot
    // tell where we are pointing". A writer that credits when it cannot tell is
    // the fail-open shape this programme has closed four times.
    for (const livemode of [true, false]) {
      const d = decideTopup(event({ livemode }), { database: 'staging' });
      expect(d.credit).toBe(false);
      if (d.credit) return;
      expect(d.reason).toBe('undeterminable_environment');
    }
    // Same for an unset/unparseable DATABASE_URL, which reaches here as ''.
    const empty = decideTopup(event(), { database: '' });
    expect(empty.credit).toBe(false);
  });

  it('an unhandled event type is refused by name, not silently ignored', () => {
    const d = decideTopup(event({ type: 'invoice.paid' }), QA);
    expect(d.credit).toBe(false);
    if (d.credit) return;
    expect(d.reason).toBe('unhandled_event_type');
  });

  it('an UNPAID session does not credit — a delayed method has not settled', () => {
    const d = decideTopup(event({}, { payment_status: 'unpaid' }), QA);
    expect(d.credit).toBe(false);
    if (d.credit) return;
    expect(d.reason).toBe('not_paid');
  });

  it('a non-USD session refuses rather than guessing the conversion', () => {
    const d = decideTopup(event({}, { currency: 'eur' }), QA);
    expect(d.credit).toBe(false);
    if (d.credit) return;
    expect(d.reason).toBe('currency_not_usd');
  });

  it('a zero, negative, missing or fractional amount is not creditable', () => {
    for (const amount_total of [0, -100, null, 1.5, Number.MAX_SAFE_INTEGER + 2]) {
      const d = decideTopup(event({}, { amount_total }), QA);
      expect(d.credit, `amount_total=${amount_total} was credited`).toBe(false);
      if (d.credit) return;
      expect(d.reason).toBe('amount_not_creditable');
    }
  });

  it('a session with no practiceId credits nothing', () => {
    const d = decideTopup(event({}, { metadata: { userId: 'user_1' } }), QA);
    expect(d.credit).toBe(false);
    if (d.credit) return;
    expect(d.reason).toBe('no_practice_in_metadata');
  });

  it('a missing userId is legal — the credit belongs to the PRACTICE', () => {
    const d = decideTopup(event({}, { metadata: { practiceId: 'prac_1' } }), QA);
    expect(d.credit).toBe(true);
    if (!d.credit) return;
    expect(d.userId).toBeNull();
  });

  // ── DISCOVERY §E.5 — the metadata allowlist. ──────────────────────────────
  it('⚠️ ANY metadata key outside the allowlist refuses the credit', () => {
    // The three §E.5 names it in as many words, plus the one a denylist misses.
    for (const key of ['visitId', 'patientId', 'billingEventId', 'customerNote']) {
      const d = decideTopup(
        event({}, { metadata: { practiceId: 'prac_1', [key]: 'x' } }),
        QA,
      );
      expect(d.credit, `metadata key "${key}" was accepted`).toBe(false);
      if (d.credit) return;
      expect(d.reason).toBe('forbidden_metadata_key');
      expect(d.detail).toContain(key);
    }
  });

  it('⚠️ the allowlist is exactly two keys — an ADDITION must be deliberate', () => {
    // Pinned by NAME because this is the guard's whole substance. A future
    // change that widened it silently would be invisible to every behavioural
    // assertion above: they would all still pass.
    expect([...ALLOWED_METADATA_KEYS].sort()).toEqual(['practiceId', 'userId']);
  });

  it('⚠️ `billingEventId` is why this is an allowlist and not a /visit|patient/ denylist', () => {
    // DISCOVERY §E.5's loaded gun: `BillingEvent` "sounds like an invoice and is
    // a CLINICAL CLAIMS RECORD with a required patientId". It matches neither
    // word, and it dereferences to a named patient just the same.
    expect(/visit|patient/i.test('billingEventId')).toBe(false);
    const d = decideTopup(
      event({}, { metadata: { practiceId: 'prac_1', billingEventId: 'be_1' } }),
      QA,
    );
    expect(d.credit).toBe(false);
  });
});

// ---------------------------------------------------------------------------
describe('B7 — the money is integer arithmetic (GATE 0.4)', () => {
  it('one cent is exactly 10 000 micro-dollars, and it is BigInt', () => {
    expect(centsToMicroUsd(1)).toBe(10_000n);
    expect(typeof centsToMicroUsd(1)).toBe('bigint');
  });

  it('a large amount survives without float error', () => {
    // $1,000,000.01 — a value that loses precision the moment a float is used
    // for the micro-dollar figure (1.0000001e14 is beyond a double's integer
    // range only later, but the multiply is where a naive `* 1e4` drifts).
    expect(centsToMicroUsd(100_000_001)).toBe(1_000_000_010_000n);
  });

  it('the idempotency key is derived from the SESSION, never the event', () => {
    // Two DIFFERENT events describing ONE session must collide on the unique
    // index — that is what stops a delayed-payment flow crediting twice.
    const a = decideTopup(event({ id: 'evt_A' }), QA);
    const b = decideTopup(event({ id: 'evt_B' }), QA);
    expect(a.credit && b.credit).toBe(true);
    if (!a.credit || !b.credit) return;
    expect(a.idempotencyKey).toBe(b.idempotencyKey);
    expect(a.idempotencyKey).toBe(topupIdempotencyKey('cs_test_1'));
  });
});

// ---------------------------------------------------------------------------
describe('B7 — the route’s source-level invariants', () => {
  it('the scan is non-vacuous: the route source and the stripped code are real', () => {
    expect(ROUTE_SRC.length, 'the route file read as (almost) empty').toBeGreaterThan(2000);
    expect(ROUTE_CODE.length, 'stripping comments removed everything').toBeGreaterThan(1500);
    expect(ROUTE_CODE).toContain('export async function POST');
  });

  it('POSITIVE CONTROL — comment stripping actually removed the prose', () => {
    // The header discusses `req.json()` at length. If stripping failed, the
    // "never calls req.json()" assertion below would go RED on a correct file —
    // and if stripping were TOO aggressive the ordering checks would all be
    // vacuous. Both directions are pinned here.
    expect(ROUTE_SRC, 'the header no longer discusses req.json()').toContain('req.json()');
    expect(ROUTE_CODE, 'comment stripping did not remove the prose').not.toContain('req.json()');
  });

  it('⚠️ the raw body is read with `req.text()` and NEVER `req.json()`', () => {
    // DISCOVERY §E.3: `JSON.stringify(await req.json())` is not byte-identical
    // to what Stripe signed, and it fails as an opaque SIGNATURE error rather
    // than a parse error — which reads as a wrong secret and sends the next
    // person to rotate credentials.
    expect(ROUTE_CODE).toContain('req.text()');
    expect(ROUTE_CODE).not.toContain('req.json()');
  });

  it('⚠️ NOTHING touches the database before the signature has verified', () => {
    const verifyAt = ROUTE_CODE.indexOf('constructEvent');
    expect(verifyAt, 'the route does not verify a signature at all').toBeGreaterThan(-1);

    // Every database-touching symbol in the file, by name. If one is added
    // later it belongs in this list; the non-vacuity assertion below is what
    // makes a forgotten entry visible rather than silently uncovered.
    for (const symbol of ['prisma.', 'logAudit(']) {
      const first = ROUTE_CODE.indexOf(symbol);
      expect(first, `${symbol} does not appear in the route at all`).toBeGreaterThan(-1);
      expect(
        first,
        `${symbol} appears BEFORE the signature check — this route is ` +
          'unauthenticated (DISCOVERY §E.4), so anything it does before verifying ' +
          'is something the open internet can make it do',
      ).toBeGreaterThan(verifyAt);
    }
  });

  it('⚠️ the fail-closed arm: no webhook secret configured means no work at all', () => {
    const secretAt = ROUTE_CODE.indexOf('STRIPE_WEBHOOK_SECRET');
    expect(secretAt, 'the route never reads STRIPE_WEBHOOK_SECRET').toBeGreaterThan(-1);
    // It is read before the body is even consumed. With the secret unset —
    // which is its state in every environment today — the route is inert.
    expect(secretAt).toBeLessThan(ROUTE_CODE.indexOf('req.text()'));
    expect(ROUTE_CODE).toContain('503');
  });

  it('⚠️ `userId` and `practiceId` are passed to every logAudit call — no session exists', () => {
    // DISCOVERY §E.6: `logAudit` calls `auth()` internally, which is
    // request-scoped. A webhook has no session, so an omitted argument does not
    // fall back to something sensible — it produces an UNATTRIBUTED row and an
    // error-level log, and on the credited path it would lose the tenant of a
    // money movement.
    //
    // ⚠️ THE MATCHER IS INDENTATION-AGNOSTIC ON PURPOSE. Its first draft closed
    // on `\n    })`, a literal four-space indent, and found 2 of the 4 calls —
    // the two at top level — while silently skipping the two nested inside
    // `if` blocks. The non-vacuity assertion below is the only reason that was
    // visible: every call it DID find passed, so the suite would have gone
    // green having checked half the file. A count is what turns "the assertions
    // passed" into "the assertions ran on everything".
    const calls = [...ROUTE_CODE.matchAll(/logAudit\(\{[\s\S]*?\n\s*\}\);/g)].map((m) => m[0]);
    const expected = (ROUTE_CODE.match(/logAudit\(\{/g) ?? []).length;
    expect(expected, 'the route contains no logAudit calls at all').toBeGreaterThanOrEqual(4);
    expect(
      calls.length,
      `the call matcher found ${calls.length} of ${expected} logAudit calls — it is ` +
        'skipping some, so the assertions below cover less than they claim',
    ).toBe(expected);
    for (const call of calls) {
      expect(call, `a logAudit call omits userId:\n${call}`).toContain('userId:');
      expect(call, `a logAudit call omits practiceId:\n${call}`).toContain('practiceId:');
    }
  });

  it('the route declares the nodejs runtime — `constructEvent` (sync) needs it', () => {
    expect(ROUTE_CODE).toContain("export const runtime = 'nodejs'");
  });

  it('⚠️ the ledger row is a POSITIVE `topup` on the `paid` bucket', () => {
    // `ledger_entries_kind_sign` CHECKs `topup > 0`; the balance is a running
    // sum, so money arriving is a positive amount. A negated amount here would
    // be refused by the database — this asserts the refusal is never reached.
    expect(ROUTE_CODE).toContain("kind: 'topup'");
    expect(ROUTE_CODE).toContain("bucket: 'paid'");
    expect(ROUTE_CODE).toContain('amountMicroUsd: decision.amountMicroUsd');
    expect(ROUTE_CODE, 'the credit is negated somewhere').not.toContain('-decision.amountMicroUsd');
  });

  it('⚠️ `balanceAfter` and `seq` are NOT sent — the trigger derives them', () => {
    // Ruling 89(d): a caller-supplied value is IGNORED, not validated. Sending
    // one is a way to believe something false about the row you just wrote.
    const createBlock = ROUTE_CODE.slice(
      ROUTE_CODE.indexOf('prisma.ledgerEntry.create'),
      ROUTE_CODE.indexOf('select:'),
    );
    expect(createBlock.length, 'the create-block slice found nothing').toBeGreaterThan(100);
    expect(createBlock).not.toContain('balanceAfter:');
    expect(createBlock).not.toContain('seq:');
  });
});
