// ============================================================================
// GATE — B7 STEP 2. WHAT MAY BECOME A CHECKOUT SESSION, AND WHERE THE PAYING
// PARTY COMES FROM.
// ----------------------------------------------------------------------------
// Step 1's gate asked what an inbound event may CREDIT. This one asks what may
// be CHARGED in the first place, and it has one clause step 1 could not have:
//
//   · the mode rule, outbound      → behavioural, pure (key mode × database)
//   · the amount allowlist         → behavioural, pure
//   · the paying party is the SESSION's, never the body's   → source
//   · the metadata this half BUILDS satisfies the allowlist the other half
//     ENFORCES                                              → cross-half contract
//
// ⚠️ THE LAST ONE IS THE REASON THIS FILE EXISTS RATHER THAN A FEW MORE CASES
// IN STEP 1's. The two halves of B7 are separated by Stripe: this code writes
// metadata, Stripe stores it, and step 1's code reads it back days later. There
// is no type between them and no test that runs both — so the contract is
// asserted here by feeding one half's OUTPUT into the other half's INPUT and
// requiring it to survive. A drift between `ALLOWED_METADATA_KEYS` and what
// this module constructs would otherwise be discovered by a doctor who had
// already paid.
//
// ⚠️ AND WHAT WOULD MAKE THIS GATE FAIL, STATED BEFORE IT IS MADE TO FAIL:
// a live key accepted on a non-production database; an unclassifiable key
// treated as test; an amount outside the denominations reaching Stripe; the
// route reading `practiceId` out of a request body; a metadata key added here
// and not to the allowlist; `success_url` derived from a request header.
// Each has a named case below, and each was mutation-proved.
// ============================================================================

import { readFileSync } from 'node:fs';

import { describe, it, expect } from 'vitest';

import {
  TOPUP_DENOMINATIONS_CENTS,
  classifyStripeSecretKey,
  decideCheckout,
  formatCentsUsd,
  type CheckoutRequestInput,
  type DbIdentity,
  type StripeKeyMode,
} from '../stripe-checkout';
import { ALLOWED_METADATA_KEYS, decideTopup, type CheckoutEventShape } from '../stripe-topup';

const ROUTE_PATH = 'src/app/api/stripe/checkout/route.ts';
const ROUTE_SRC = readFileSync(ROUTE_PATH, 'utf8');
/** Comments stripped. Every source assertion is measured on THIS — the route's
 *  header discusses request bodies, `Host` headers and `practiceId` at length,
 *  and scanning the raw text would report what the prose says. Fifth sighting
 *  of the substring family in AGENTS.md. */
const ROUTE_CODE = ROUTE_SRC.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');

const SETTINGS_PATH = 'src/app/settings/page.tsx';
const SETTINGS_SRC = readFileSync(SETTINGS_PATH, 'utf8');

const PROD: DbIdentity = { database: 'meddoc', host: 'postgres' };
const QA: DbIdentity = { database: 'meddoc_qa_test', host: 'postgres' };
/** Confirmed by NEITHER guard — the deliberate gap of ruling 90(c). */
const UNKNOWN: DbIdentity = { database: 'staging', host: 'postgres' };

function input(over: Partial<CheckoutRequestInput> = {}): CheckoutRequestInput {
  return { practiceId: 'prac_1', userId: 'user_1', amountCents: 5_000, ...over };
}

// ---------------------------------------------------------------------------
describe('B7 step 2 — the secret key names its own mode', () => {
  const cases: [string, StripeKeyMode][] = [
    ['sk_test_51abcdef', 'test'],
    ['rk_test_51abcdef', 'test'],
    ['sk_live_51abcdef', 'live'],
    ['rk_live_51abcdef', 'live'],
    // ⚠️ THE LITERAL QA'S COMPOSE FILE DECLARES. It must classify as
    // `unrecognised` — that is what makes the whole route walkable on QA with
    // no Stripe account, and it is a value somebody could "helpfully" replace
    // with a real-looking `sk_test_` string.
    ['qa-dummy-stripe-secret-never-valid', 'unrecognised'],
    ['pk_test_51abcdef', 'unrecognised'],
    ['sk_51abcdef', 'unrecognised'],
    ['sk_TEST_51abcdef', 'unrecognised'],
    ['', 'absent'],
    ['   ', 'absent'],
  ];

  for (const [key, expected] of cases) {
    it(`"${key}" is ${expected}`, () => {
      expect(classifyStripeSecretKey(key)).toBe(expected);
    });
  }

  it('undefined and null are absent, not unrecognised', () => {
    expect(classifyStripeSecretKey(undefined)).toBe('absent');
    expect(classifyStripeSecretKey(null)).toBe('absent');
  });
});

// ---------------------------------------------------------------------------
describe('B7 step 2 — MODE: the outbound mirror of ruling 91(a)', () => {
  it('production + a LIVE key creates', () => {
    const d = decideCheckout(input(), PROD, 'live');
    expect(d.create).toBe(true);
  });

  it('a non-production database + a TEST key creates', () => {
    const d = decideCheckout(input(), QA, 'test');
    expect(d.create).toBe(true);
  });

  it('⚠️ a LIVE key may NOT create a session from a non-production environment', () => {
    const d = decideCheckout(input(), QA, 'live');
    expect(d).toMatchObject({ create: false, reason: 'mode_mismatch' });
    // The hard-halt direction: a real card charged from a test system.
    expect(d.create === false && d.detail).toContain('real card');
  });

  it('a TEST key may not create a session on production either', () => {
    const d = decideCheckout(input(), PROD, 'test');
    expect(d).toMatchObject({ create: false, reason: 'mode_mismatch' });
  });

  it('⚠️ an UNIDENTIFIABLE database refuses in BOTH key modes — the gap is deliberate', () => {
    for (const mode of ['live', 'test'] as const) {
      const d = decideCheckout(input(), UNKNOWN, mode);
      expect(d).toMatchObject({ create: false, reason: 'undeterminable_environment' });
    }
  });

  it('an ABSENT key refuses before mode is even considered — the fail-closed arm', () => {
    // Note the database here is UNKNOWN: if configuration were checked after
    // mode, this would report `undeterminable_environment` instead.
    const d = decideCheckout(input(), UNKNOWN, 'absent');
    expect(d).toMatchObject({ create: false, reason: 'not_configured' });
  });

  it('⚠️ an UNRECOGNISED key is refused BY NAME, never silently treated as test', () => {
    for (const db of [PROD, QA, UNKNOWN]) {
      const d = decideCheckout(input(), db, 'unrecognised');
      expect(d).toMatchObject({ create: false, reason: 'unrecognised_key_mode' });
    }
  });

  it('mode is settled BEFORE the amount is read', () => {
    // A nonsense amount AND a mode mismatch: the mode must be the reported one.
    const d = decideCheckout(input({ amountCents: 'nope' }), QA, 'live');
    expect(d).toMatchObject({ create: false, reason: 'mode_mismatch' });
  });
});

// ---------------------------------------------------------------------------
describe('B7 step 2 — the amount is an ALLOWLIST, not a bound', () => {
  it('every offered denomination is accepted', () => {
    for (const cents of TOPUP_DENOMINATIONS_CENTS) {
      const d = decideCheckout(input({ amountCents: cents }), QA, 'test');
      expect(d).toMatchObject({ create: true, amountCents: cents });
    }
  });

  it('⚠️ a value BETWEEN two denominations is refused — which a bound would admit', () => {
    const [lo, hi] = [TOPUP_DENOMINATIONS_CENTS[0], TOPUP_DENOMINATIONS_CENTS[1]];
    const between = Math.trunc((lo + hi) / 2);
    expect(TOPUP_DENOMINATIONS_CENTS).not.toContain(between);
    const d = decideCheckout(input({ amountCents: between }), QA, 'test');
    expect(d).toMatchObject({ create: false, reason: 'amount_not_offered' });
  });

  it('a huge, zero, negative, fractional, string or missing amount is refused', () => {
    for (const bad of [0, -5_000, 5_000.5, '5000', null, undefined, 1e30, NaN, [5_000]]) {
      const d = decideCheckout(input({ amountCents: bad }), QA, 'test');
      expect(d, `amountCents=${JSON.stringify(bad)}`).toMatchObject({
        create: false,
        reason: 'amount_not_offered',
      });
    }
  });

  it('⚠️ the denominations are FACE VALUE — no bonus, no discount, no tier', () => {
    // Each entry buys exactly its own cents of credit; the mapping cents →
    // micro-dollars is step 1's `centsToMicroUsd`, which is × 10 000 flat.
    // A denomination list carrying a bonus would be a PRICING decision, which
    // is a hard halt on this programme. Asserted as round dollar amounts with
    // nothing clever in them.
    for (const cents of TOPUP_DENOMINATIONS_CENTS) {
      expect(cents % 100).toBe(0);
      expect(Number.isSafeInteger(cents)).toBe(true);
      expect(cents).toBeGreaterThan(50); // Stripe's own USD minimum
    }
    expect([...TOPUP_DENOMINATIONS_CENTS]).toEqual([2_500, 5_000, 10_000, 25_000]);
  });

  it('the display string is integer arithmetic (GATE 0.4 — no float near money)', () => {
    expect(formatCentsUsd(2_500)).toBe('$25.00');
    expect(formatCentsUsd(10_000)).toBe('$100.00');
    expect(formatCentsUsd(1)).toBe('$0.01');
    expect(formatCentsUsd(1_099)).toBe('$10.99');
  });
});

// ---------------------------------------------------------------------------
describe('B7 step 2 — the paying party', () => {
  it('a session with no practice creates nothing', () => {
    for (const missing of [null, undefined, '', '   ']) {
      const d = decideCheckout(input({ practiceId: missing }), QA, 'test');
      expect(d).toMatchObject({ create: false, reason: 'no_practice_in_session' });
    }
  });

  it('⚠️ a missing userId ALSO refuses — unlike the webhook, which has no session', () => {
    // Step 1 accepts a null `userId` because it genuinely has no session. Here
    // the route authenticates first, so an absent user id means something is
    // wrong rather than unknown, and an unattributable charge is refused.
    const d = decideCheckout(input({ userId: null }), QA, 'test');
    expect(d).toMatchObject({ create: false, reason: 'no_practice_in_session' });
  });

  it('the ids are trimmed, and the decision carries exactly what it was given', () => {
    const d = decideCheckout(input({ practiceId: ' prac_9 ', userId: ' user_9 ' }), QA, 'test');
    expect(d).toMatchObject({ create: true, practiceId: 'prac_9', userId: 'user_9' });
  });
});

// ---------------------------------------------------------------------------
describe('B7 — THE CROSS-HALF CONTRACT: what step 2 builds, step 1 accepts', () => {
  it('the constructed metadata is EXACTLY the allowlist, and is imported not restated', () => {
    const d = decideCheckout(input(), QA, 'test');
    expect(d.create).toBe(true);
    if (!d.create) return;
    expect(Object.keys(d.metadata).sort()).toEqual([...ALLOWED_METADATA_KEYS].sort());
  });

  it('⚠️ step 2 output → step 1 input round-trips WITHOUT a metadata refusal', () => {
    const d = decideCheckout(input({ amountCents: 10_000 }), QA, 'test');
    expect(d.create).toBe(true);
    if (!d.create) return;

    // Stripe echoes session metadata back on the event. Build the event the
    // webhook would receive for the session this decision describes.
    const echoed: CheckoutEventShape = {
      id: 'evt_roundtrip',
      type: 'checkout.session.completed',
      livemode: false, // QA identity on both sides — the modes agree
      data: {
        object: {
          id: 'cs_roundtrip',
          amount_total: d.amountCents,
          currency: 'usd',
          payment_status: 'paid',
          metadata: d.metadata,
        },
      },
    };

    const credit = decideTopup(echoed, QA);
    expect(credit).toMatchObject({
      credit: true,
      practiceId: 'prac_1',
      userId: 'user_1',
      // 10 000 cents = $100 = 100 000 000 micro-dollars.
      amountMicroUsd: 100_000_000n,
    });
  });

  it('POSITIVE CONTROL — the round-trip CAN fail, so its pass means something', () => {
    // The same event with one extra metadata key is refused by step 1. Without
    // this, a round-trip that silently stopped checking metadata would look
    // identical to one that passes.
    const poisoned: CheckoutEventShape = {
      id: 'evt_roundtrip_bad',
      type: 'checkout.session.completed',
      livemode: false,
      data: {
        object: {
          id: 'cs_roundtrip_bad',
          amount_total: 10_000,
          currency: 'usd',
          payment_status: 'paid',
          metadata: { practiceId: 'prac_1', userId: 'user_1', billingEventId: 'be_1' },
        },
      },
    };
    expect(decideTopup(poisoned, QA)).toMatchObject({
      credit: false,
      reason: 'forbidden_metadata_key',
    });
  });

  it('the product name carries no practice, patient, visit or person', () => {
    const d = decideCheckout(input(), QA, 'test');
    if (!d.create) throw new Error('expected a decision');
    expect(d.productName).toBe('QuillMD credit — $50.00');
    expect(d.productName).not.toContain('prac_1');
    expect(d.productName).not.toContain('user_1');
  });
});

// ---------------------------------------------------------------------------
describe("B7 step 2 — the route's source-level invariants", () => {
  it('the scan is non-vacuous: the route source and the stripped code are real', () => {
    expect(ROUTE_SRC.length).toBeGreaterThan(2_000);
    expect(ROUTE_CODE.length).toBeGreaterThan(800);
    expect(ROUTE_CODE).toContain('decideCheckout');
  });

  it('POSITIVE CONTROL — comment stripping actually removed the prose', () => {
    // A phrase that exists ONLY in the header. If stripping silently no-opped,
    // every ordering assertion below would be measured on the commentary.
    expect(ROUTE_SRC).toContain('No PAN ever reaches this system');
    expect(ROUTE_CODE).not.toContain('No PAN ever reaches this system');
  });

  it('⚠️ THE PAYING PARTY IS READ FROM THE SESSION, NEVER FROM THE BODY', () => {
    // The one field taken out of the request body is `amountCents`, and it is
    // the only property the body is destructured for.
    expect(ROUTE_CODE).toContain('amountCents');
    expect(ROUTE_CODE).toContain('session.user.practiceId');
    // No body-sourced practice or user, in any spelling that would compile.
    for (const forbidden of [
      'body.practiceId',
      'body.userId',
      'practiceId?: unknown',
      'userId?: unknown',
    ]) {
      expect(ROUTE_CODE, `route must not read ${forbidden} from the request`).not.toContain(
        forbidden,
      );
    }
    // And the decision is handed the session's values verbatim.
    expect(ROUTE_CODE.replace(/\s+/g, ' ')).toContain(
      '{ practiceId: session.user.practiceId, userId, amountCents }',
    );
  });

  it('⚠️ authentication happens BEFORE the body is read and before any decision', () => {
    const code = ROUTE_CODE;
    const authAt = code.indexOf('getSession(');
    const bodyAt = code.indexOf('req.json(');
    const decideAt = code.indexOf('decideCheckout(');
    const stripeAt = code.indexOf('new Stripe(');
    expect(authAt).toBeGreaterThan(-1);
    expect(bodyAt).toBeGreaterThan(authAt);
    expect(decideAt).toBeGreaterThan(bodyAt);
    expect(stripeAt).toBeGreaterThan(decideAt);
  });

  it('⚠️ the RETURN URLS come from a server constant, never from the request', () => {
    expect(ROUTE_CODE).toContain('success_url: `${APP_URL}');
    expect(ROUTE_CODE).toContain('cancel_url: `${APP_URL}');
    // A caller-controlled origin must never reach a redirect target.
    for (const forbidden of ['req.headers.get(', 'req.url', 'headers().get(']) {
      expect(ROUTE_CODE, `return URLs must not derive from ${forbidden}`).not.toContain(forbidden);
    }
  });

  it('⚠️ the metadata sent to Stripe is the DECISION’s, with nothing added at the call site', () => {
    // ⚠️ SCOPED TO THE STRIPE CALL, AND THE SCOPING IS THE POINT. A file-wide
    // ban on `metadata: {` measures a wider universe than the claim: the two
    // `logAudit` rows carry inline metadata literals and are SUPPOSED to. The
    // first draft of this assertion banned them too and went red on correct
    // code — a check whose name was narrower than what it measured, caught by
    // the run rather than by re-reading it.
    const createAt = ROUTE_CODE.indexOf('sessions.create(');
    expect(createAt).toBeGreaterThan(-1);
    const endAt = ROUTE_CODE.indexOf('checkoutUrl =', createAt);
    expect(endAt).toBeGreaterThan(createAt);
    const createArg = ROUTE_CODE.slice(createAt, endAt);

    // Non-vacuity: the window really is the Checkout call's argument.
    expect(createArg).toContain('line_items');
    expect(createArg).toContain('unit_amount');

    expect(createArg.replace(/\s+/g, ' ')).toContain('metadata: decision.metadata,');
    // No inline object literal for metadata HERE — that is the shape that drifts
    // away from `ALLOWED_METADATA_KEYS` without anything noticing.
    expect(createArg).not.toMatch(/metadata:\s*\{/);
  });

  it('the secret key is never logged or returned — only its classification is', () => {
    expect(ROUTE_CODE).toContain('keyMode');
    expect(ROUTE_CODE).not.toMatch(/(secretKey|STRIPE_SECRET_KEY)\s*[,}]\s*\n?\s*\}\s*,?\s*\)/);
    // The audit metadata records `keyMode`, and `secretKey` appears exactly
    // twice: where it is read, and where it constructs the client.
    const occurrences = ROUTE_CODE.split('secretKey').length - 1;
    expect(occurrences).toBe(3); // declaration + classify + `new Stripe(...)`
  });

  it('every refusal path writes an audit row — this route IS authenticated', () => {
    // Contrast with the webhook, whose pre-verification refusals deliberately
    // write nothing (ruling 91(b)). Here the refusal rate is bounded by a
    // logged-in user's rate limit, so the ordinary convention applies.
    const refusedRows = ROUTE_CODE.split("action: 'CHECKOUT_SESSION_REFUSED'").length - 1;
    expect(refusedRows).toBe(2); // the decision refusal, and a failed Stripe call
    expect(ROUTE_CODE).toContain("action: 'CHECKOUT_SESSION_CREATED'");
  });

  it('the route is rate-limited and declares the nodejs runtime', () => {
    expect(ROUTE_CODE).toContain('rateLimitOr429');
    expect(ROUTE_CODE).toContain("runtime = 'nodejs'");
  });
});

// ---------------------------------------------------------------------------
describe('B7 step 2 — the settings door', () => {
  it('⚠️ the door is gated on PRESENCE of a key, read on the SERVER', () => {
    expect(SETTINGS_SRC).toContain(
      "const topupConfigured = (process.env.STRIPE_SECRET_KEY ?? '').trim().length > 0;",
    );
    expect(SETTINGS_SRC).toContain('{topupConfigured ? (');
    expect(SETTINGS_SRC).toContain('<BillingTopupPanel />');
  });

  it('⚠️ with no key configured the OLD placeholder still renders — today’s production', () => {
    // Production has no `STRIPE_SECRET_KEY`, so this branch is what ships. The
    // deploy declaration's "nothing but the image ids" depends on it.
    expect(SETTINGS_SRC).toContain('Billing is handled for you during the pilot.');
    expect(SETTINGS_SRC).toContain('Manage billing');
  });

  it('the panel sends ONLY an amount — no practice or user field exists in it', () => {
    const PANEL = readFileSync('src/app/settings/billing-topup-panel.tsx', 'utf8');
    const code = PANEL.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
    expect(code).toContain('JSON.stringify({ amountCents })');
    expect(code).not.toContain('practiceId');
    expect(code).not.toContain('userId');
    // And it offers exactly the shared constant, never its own copy.
    expect(code).toContain('TOPUP_DENOMINATIONS_CENTS.map');
  });
});
