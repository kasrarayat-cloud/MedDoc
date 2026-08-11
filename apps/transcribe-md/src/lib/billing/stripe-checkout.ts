// ============================================================================
// FOUNDATION B7 STEP 2 — WHAT MAY BECOME A STRIPE CHECKOUT SESSION
// ----------------------------------------------------------------------------
// SPEC §2.3: "Stripe Checkout only. No PAN ever reaches this system." RELAY B7:
// "Hosted Checkout only — it avoids the publishable key and its build-arg
// inlining trap entirely (DISCOVERY §E.7)."
//
// Step 1 built the INBOUND half — the webhook that credits a wallet when Stripe
// says a session was paid. This is the OUTBOUND half: the only thing in this
// system that may ask Stripe to take somebody's money.
//
// ── THE SAME TWO-HALVES SPLIT AS B6 AND B7 STEP 1 ─────────────────────────
//
//   1. `decideCheckout` — PURE. An authenticated identity, a requested amount,
//      a database identity and a key mode in; a decision out. No network, no
//      database, no clock, no `process.env`.
//   2. the route (`app/api/stripe/checkout/route.ts`) — authenticates, reads
//      the environment, applies the decision, and is the only thing that talks
//      to Stripe.
//
// The reason is the one B6's header gives: a decision that refuses off
// production can never be watched SUCCEEDING by any test we are allowed to run,
// so the decision has to be provable from literals somewhere the tests reach.
//
// ============================================================================
// ⚠️ (a) THE PAYING PARTY COMES FROM THE SESSION, NEVER FROM THE REQUEST
// ----------------------------------------------------------------------------
// This module accepts an AMOUNT from the caller and nothing else. `practiceId`
// and `userId` are resolved server-side from the authenticated session and
// handed in; there is no code path by which a request body can name them.
//
// ⚠️ AND THAT IS WHAT MAKES STEP 1's METADATA ALLOWLIST MEAN ANYTHING. Stripe
// echoes session metadata back on the event, so the inbound allowlist
// (`ALLOWED_METADATA_KEYS`) can only ever catch what OUR OWN code put there —
// step 1's header says so in as many words: "what this actually catches is our
// own session-creation code (B7 step 2) putting something forbidden there".
// This file is that code. If it built metadata from a request body, the
// allowlist would be guarding a value an anonymous caller chose, and DISCOVERY
// §E.5's whole concern — a visit id dereferences to a named patient in ONE hop —
// would arrive through the front door with a valid signature on it.
//
// So the metadata is not merely validated here, it is CONSTRUCTED from the two
// server-known values and then checked against step 1's own constant, which is
// IMPORTED rather than restated. Two literals would both stay green while
// drifting apart (AGENTS.md — prefer DERIVING over threading a copy).
//
// ============================================================================
// ⚠️ (b) MODE — THE OUTBOUND MIRROR OF RULING 91(a)
// ----------------------------------------------------------------------------
// Ruling 91(a) settled the inbound rule: an event's `livemode` must match the
// database, both confirmed positively, with anything unidentifiable refusing
// BOTH ways. The outbound question has the same two facts and therefore takes
// the same shape — except that here the mode is carried by the SECRET KEY:
//
//     production database  + a LIVE secret key  → create
//     non-prod database    + a TEST secret key  → create
//     everything else                            → REFUSE
//
// ⚠️ NOTE WHICH DIRECTION IS THE DANGEROUS ONE, AND IT IS NOT THE SAME AS THE
// WEBHOOK'S. Inbound, the reachable-today hazard was `prod + test event` — a
// credit nobody paid for. Outbound it is `non-prod + LIVE key`: a staging or QA
// box that can charge a real card. That is a FOUNDATION hard-halt item
// ("anything charging a real card"), and it is the reason this refuses on a key
// whose mode it cannot classify rather than trying the call and seeing.
//
// ⚠️ AND THE UNRECOGNISED-KEY ARM IS LOAD-BEARING ON QA TODAY. QA's compose
// declares `STRIPE_SECRET_KEY: "qa-dummy-stripe-secret-never-valid"` — a
// deliberate literal that matches neither `sk_test_` nor `sk_live_`. It is
// therefore classified `unrecognised` and refused BEFORE any SDK call, which is
// what lets this route be exercised end to end on QA with no network, no Stripe
// account and no test key, exactly as B7's gate requires.
//
// ============================================================================
// ⚠️ (c) THE AMOUNT IS AN ALLOWLIST OF FACE-VALUE DENOMINATIONS
// ----------------------------------------------------------------------------
// The caller does not send an integer that becomes a charge. It sends one of a
// fixed set of amounts declared here, and anything else refuses.
//
// ⚠️ THIS IS DELIBERATELY NOT A PRICING DECISION, AND THE DISTINCTION MATTERS
// BECAUSE PRICING IS A HARD HALT ON THIS PROGRAMME. Every denomination buys
// credit at FACE VALUE — $50 buys 50 000 000 micro-dollars of wallet balance,
// one to one. There is no discount, no bonus tier and no volume break, because
// each of those WOULD be a pricing claim and none is authorised. The price of
// the service is settled elsewhere and unchanged: GATE 0.4's `cost × 3 / 2`,
// applied when usage is metered (B6), not when money is added.
//
// The allowlist form is the same argument as step 1's metadata guard. A bound
// (`min <= cents <= max`) would admit every value in between, so the set of
// amounts that can reach Stripe would be defined by arithmetic rather than by a
// diff somebody reviewed; a fixed set makes each admissible charge a named
// constant, and widening it a deliberate edit.
// ============================================================================

import { checkNonProdDb, checkProdDb } from '@meddoc/db/guard';

import { ALLOWED_METADATA_KEYS } from './stripe-topup';

/**
 * The top-up denominations, in cents, that this system will ask Stripe to
 * charge. See header (c): FACE VALUE, no bonus, no discount, no tier.
 *
 * Stripe's own USD minimum is $0.50; every entry here is far above it, so a
 * refusal from Stripe on grounds of amount is not a case this list can produce.
 */
export const TOPUP_DENOMINATIONS_CENTS: readonly number[] = [
  2_500, // $25
  5_000, // $50
  10_000, // $100
  25_000, // $250
];

/**
 * How a Stripe secret key identifies its own mode. Stripe's key prefixes are
 * `sk_` (standard) and `rk_` (restricted), each followed by `test_` or `live_`.
 *
 * `unrecognised` is a POSITIVE state, not a fallback: it is what a placeholder,
 * a truncated paste or a rotated-to-nothing value classifies as, and it refuses.
 */
export type StripeKeyMode = 'live' | 'test' | 'unrecognised' | 'absent';

/**
 * CLASSIFY A SECRET KEY BY ITS OWN PREFIX — never by which environment we think
 * we are in, which is the fact this is being cross-checked against.
 *
 * ⚠️ THE UNKNOWN CASE IS NOT SILENTLY TREATED AS TEST. A key that cannot be
 * classified refuses in both environments (see {@link decideCheckout}), which is
 * the two-positive-confirmations shape of ruling 90(c) applied to a credential
 * instead of to a database name.
 */
export function classifyStripeSecretKey(key: string | undefined | null): StripeKeyMode {
  const k = (key ?? '').trim();
  if (!k) return 'absent';
  if (/^(sk|rk)_live_/.test(k)) return 'live';
  if (/^(sk|rk)_test_/.test(k)) return 'test';
  return 'unrecognised';
}

/** Which database this process is pointed at, as the guards describe it.
 *  Structurally identical to `stripe-topup.ts`'s — both are passed in rather
 *  than read, so the mode rule is provable from a literal. */
export interface DbIdentity {
  database: string;
  host?: string;
}

/** Everything the decision needs. Note what is NOT here: no `Request`, no
 *  headers, no origin — nothing the caller controls except `amountCents`. */
export interface CheckoutRequestInput {
  /** From the authenticated session. Never from a request body. */
  practiceId: string | null | undefined;
  /** From the authenticated session. Never from a request body. */
  userId: string | null | undefined;
  /** THE ONLY caller-supplied value, and it is checked against the allowlist.
   *  Typed `unknown` because it arrives from JSON and `1e3`, `"5000"`, `null`
   *  and `5000.5` are all things a body can carry. */
  amountCents: unknown;
}

export type CheckoutRefusal =
  /** No secret key configured. The route turns this into a 503. */
  | 'not_configured'
  /** The key's prefix identifies neither mode. See {@link classifyStripeSecretKey}. */
  | 'unrecognised_key_mode'
  /** Neither database guard could positively confirm the environment. */
  | 'undeterminable_environment'
  /** The key's mode and the database's identity disagree. See header (b). */
  | 'mode_mismatch'
  /** The caller's session carries no practice — there is no wallet to fill. */
  | 'no_practice_in_session'
  /** The amount is not one of {@link TOPUP_DENOMINATIONS_CENTS}. */
  | 'amount_not_offered';

export type CheckoutDecision =
  | {
      create: true;
      practiceId: string;
      userId: string;
      amountCents: number;
      /** EXACTLY what goes to Stripe. Constructed here, keys checked against
       *  step 1's imported allowlist — see header (a). */
      metadata: Record<string, string>;
      /** What the doctor sees on the Checkout page. PHI-free by construction:
       *  a fixed noun and an integer, no patient, no visit, no practice name. */
      productName: string;
    }
  | { create: false; reason: CheckoutRefusal; detail: string };

/** Cents → a display string, for the Checkout line item only. Integer division
 *  and a padded remainder: no float touches money (GATE 0.4). */
export function formatCentsUsd(cents: number): string {
  const whole = Math.trunc(cents / 100);
  const rest = cents % 100;
  return `$${whole}.${String(rest).padStart(2, '0')}`;
}

/**
 * DECIDE WHETHER A CHECKOUT SESSION MAY BE CREATED, AND FOR WHAT.
 *
 * PURE. Every refusal is named rather than collapsed into a boolean, for the
 * same reason step 1's are: an attempt that created nothing is only auditable if
 * the reason survives, and this route IS authenticated, so — unlike the webhook —
 * auditing its refusals is bounded by a logged-in user's rate limit rather than
 * by an anonymous caller's enthusiasm.
 *
 * ⚠️ THE ORDER IS DELIBERATE AND IT IS THE SAME AS STEP 1's: configuration and
 * mode are settled BEFORE the payload is read, so a live key on a QA box is
 * refused without this code ever forming an opinion about an amount.
 */
export function decideCheckout(
  input: CheckoutRequestInput,
  db: DbIdentity,
  keyMode: StripeKeyMode,
): CheckoutDecision {
  const refuse = (reason: CheckoutRefusal, detail: string): CheckoutDecision => ({
    create: false,
    reason,
    detail,
  });

  // ── CONFIGURATION. Fail closed on an unconfigured system. ────────────────
  if (keyMode === 'absent') {
    return refuse('not_configured', 'STRIPE_SECRET_KEY is not configured — no session can be created');
  }
  if (keyMode === 'unrecognised') {
    return refuse(
      'unrecognised_key_mode',
      'the configured Stripe secret key matches neither sk_test_/rk_test_ nor sk_live_/rk_live_ — ' +
        'refusing to ask a key of unknown mode to take money',
    );
  }

  // ── MODE. Two positive confirmations, never one and its negation. ────────
  const isProd = checkProdDb(db.database, db.host).ok;
  const isNonProd = checkNonProdDb(db.database, db.host).ok;
  if (!isProd && !isNonProd) {
    return refuse(
      'undeterminable_environment',
      `database "${db.database}" is confirmed neither production nor non-production — ` +
        `refusing to create a charge from an environment whose identity is unknown`,
    );
  }
  const keyIsLive = keyMode === 'live';
  if (isProd !== keyIsLive) {
    return refuse(
      'mode_mismatch',
      isProd
        ? 'a TEST-mode Stripe key may not create a session on PRODUCTION — the payment would never credit ' +
          '(ruling 91(a) refuses the resulting test-mode event)'
        : 'a LIVE-mode Stripe key may not create a session from a NON-PRODUCTION environment — ' +
          'that is a real card being charged from a test system',
    );
  }

  // ── THE PAYING PARTY. From the session, and it must exist. ───────────────
  const practiceId = (input.practiceId ?? '').trim();
  const userId = (input.userId ?? '').trim();
  if (!practiceId) {
    return refuse(
      'no_practice_in_session',
      'the authenticated session carries no practiceId — there is no wallet to credit',
    );
  }
  if (!userId) {
    // Unreachable through the route (it authenticates first), and refused here
    // anyway: `userId` is what makes the audit row attributable, and step 1's
    // webhook accepts a null one only because it genuinely has no session.
    return refuse(
      'no_practice_in_session',
      'the authenticated session carries no userId — refusing to create an unattributable charge',
    );
  }

  // ── THE AMOUNT. Allowlist, never a bound. See header (c). ────────────────
  const cents = input.amountCents;
  if (
    typeof cents !== 'number' ||
    !Number.isSafeInteger(cents) ||
    !TOPUP_DENOMINATIONS_CENTS.includes(cents)
  ) {
    return refuse(
      'amount_not_offered',
      `amount ${JSON.stringify(cents)} is not one of the offered denominations ` +
        `(${TOPUP_DENOMINATIONS_CENTS.join(', ')} cents)`,
    );
  }

  // ── THE METADATA. Built from the two server-known values, then checked
  //     against step 1's OWN constant — imported, never restated. ───────────
  const metadata: Record<string, string> = { practiceId, userId };
  const stray = Object.keys(metadata).filter((k) => !ALLOWED_METADATA_KEYS.includes(k));
  if (stray.length > 0) {
    // Unreachable while the two constants agree, and that is the point: if a
    // future edit adds a key here without adding it to the allowlist, the
    // session is refused at the source rather than accepted here and refused
    // by the webhook after the doctor has already paid.
    return refuse(
      'no_practice_in_session',
      `constructed metadata carries ${stray.length} key(s) outside ALLOWED_METADATA_KEYS: ${stray.join(', ')}`,
    );
  }

  return {
    create: true,
    practiceId,
    userId,
    amountCents: cents,
    metadata,
    productName: `QuillMD credit — ${formatCentsUsd(cents)}`,
  };
}
