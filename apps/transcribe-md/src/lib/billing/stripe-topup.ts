// ============================================================================
// FOUNDATION B7 — WHAT A STRIPE CHECKOUT EVENT IS ALLOWED TO CREDIT
// ----------------------------------------------------------------------------
// RELAY B7: "Hosted Checkout only … signature verification is the FIRST
// statement in the handler; `req.text()` before anything, never `req.json()`.
// The webhook passes `userId` and `practiceId` explicitly; it has no session.
// FORBIDDEN in metadata: visit ids, patient ids, and anything reachable from
// `BillingEvent`."
//
// ── THE FILE IS IN TWO HALVES, AND THE SPLIT IS THE SAME ONE B6 MADE ───────
//
//   1. `decideTopup` — PURE. An event shape and a database identity in, a
//      decision out. No network, no database, no clock, no `process.env`.
//   2. the route (`app/api/stripe/webhook/route.ts`) — verifies the signature
//      and applies the decision. It is the only thing that writes.
//
// B6's header explains why: a writer that refuses off production "can never be
// watched WRITING by any test we are allowed to run", so the DECISION has to be
// provable somewhere the tests can reach. The same argument applies here twice
// over, because this decision ALSO refuses off production — see MODE below.
//
// ============================================================================
// ⚠️ MODE — WHY A TEST-MODE EVENT MAY NOT CREDIT THE PRODUCTION LEDGER
// ----------------------------------------------------------------------------
// The FOUNDATION guardrail is absolute and it is a HARD HALT item: Stripe is
// TEST MODE ONLY on this programme. So the only events that can exist today are
// test-mode events — and a test-mode `checkout.session.completed` crediting a
// real practice's real wallet is a CREDIT NOBODY PAID FOR, written into a table
// that cannot delete it.
//
// That guardrail is therefore enforced here, in code, rather than by everyone
// remembering it:
//
//     production database  + livemode: true   → credit
//     non-prod database    + livemode: false  → credit
//     everything else                          → REFUSE
//
// ⚠️ AND IT IS TWO POSITIVE CONFIRMATIONS, NOT ONE AND ITS NEGATION — ruling
// 90(c), applied verbatim. `checkProdDb` and `checkNonProdDb` are deliberately
// NOT complements: a database called `staging` is confirmed by neither and
// refused by both. That gap is the set "we cannot tell where we are pointing",
// and a top-up writer that credits money whenever it cannot tell is the
// fail-open shape this programme has now closed four times.
//
// ⚠️ NOTE WHICH DIRECTION IS THE DANGEROUS ONE. `prod + test-mode` is the one
// the guardrail is about and the one that is reachable TODAY — a test webhook
// endpoint pointed at app.quillmd.com. `non-prod + live-mode` is money that
// really moved being recorded in a ledger nobody bills from, which is a lost
// record rather than an invented one. Both refuse; only the first is a scenario
// somebody can create by accident this week.
//
// ============================================================================
// ⚠️ METADATA IS AN ALLOWLIST, AND THAT IS THE WHOLE POINT
// ----------------------------------------------------------------------------
// DISCOVERY §E.5 names what must never reach Stripe: visit ids and patient ids,
// because `transcribe_visits` carries `patientName` and `patientSummary` AS
// COLUMNS — a visit id dereferences to a named patient in ONE hop. It also
// names the loaded gun: `BillingEvent` "sounds like an invoice and is a
// CLINICAL CLAIMS RECORD with a required `patientId`", holding 0 rows, which
// makes the trap quieter rather than smaller.
//
// The obvious guard is a denylist — reject keys matching /visit|patient/. That
// is a HAND-KEPT LIST, and AGENTS.md is explicit that hand-kept lists are wrong
// eventually: `billingEventId` matches neither word and dereferences to a named
// patient just the same.
//
// So the rule is inverted. The metadata keys must be a SUBSET of
// {@link ALLOWED_METADATA_KEYS}, and anything else refuses the credit. A key
// added in five years is refused by default and its admission is a deliberate
// edit to one named constant, in a diff somebody reviews — which is the
// opposite failure mode from a pattern that silently stops matching.
//
// ⚠️ AND THIS GUARD RUNS ON THE INBOUND EVENT, WHICH IS THE WEAKER HALF.
// Stripe echoes back whatever metadata the session was created with, so what
// this actually catches is OUR OWN session-creation code (B7 step 2) putting
// something forbidden there — a regression, not an attacker. An attacker who
// could set session metadata could already forge the signature. It is a
// tripwire on our own future carelessness, and it is worth having for exactly
// that reason: the §E.5 mistake is one an implementer makes by grepping for
// `billing` and landing on the wrong table.
// ============================================================================

import { checkNonProdDb, checkProdDb } from '@meddoc/db/guard';

/**
 * The ONLY metadata keys a Checkout Session may carry. See the header — this is
 * an allowlist because a denylist decays and this one guards PHI reachability.
 *
 * `practiceId` is the paying party and `userId` is who clicked. DISCOVERY §E.5:
 * both are "personal data, but not PHI" — at ~197 practices to ~196 users a
 * practice id is effectively a clinician identity, which is stated so nobody
 * reads "safe" as "anonymous".
 */
export const ALLOWED_METADATA_KEYS: readonly string[] = ['practiceId', 'userId'];

/**
 * The subset of a Stripe `checkout.session.completed` event this module reads.
 * STRUCTURAL, so the pure core needs no Stripe import and the gate can drive it
 * from an object literal — the same reason B6's `ChargeableUsageRow` exists.
 */
export interface CheckoutEventShape {
  id: string;
  type: string;
  livemode: boolean;
  data: {
    object: {
      id: string;
      /** Smallest currency unit — cents for USD. Integer, per Stripe's API. */
      amount_total: number | null;
      currency: string | null;
      payment_status: string | null;
      metadata: Record<string, string> | null;
    };
  };
}

/** Which database this process is pointed at, as the guards describe it. */
export interface DbIdentity {
  database: string;
  host?: string;
}

export type TopupRefusal =
  /** Not an event we handle. Not a fault — Stripe sends what it is subscribed to. */
  | 'unhandled_event_type'
  /** The event's livemode does not match the database's identity. See MODE. */
  | 'mode_mismatch'
  /** Neither guard could positively confirm the environment. See MODE. */
  | 'undeterminable_environment'
  /** `payment_status` is not `paid` — a delayed method has not settled yet. */
  | 'not_paid'
  /** Not USD. The micro-dollar conversion would be wrong, so it is not made. */
  | 'currency_not_usd'
  /** No amount, or an amount that is not a positive integer number of cents. */
  | 'amount_not_creditable'
  /** No `practiceId` in metadata — nothing to credit. */
  | 'no_practice_in_metadata'
  /** A metadata key outside the allowlist. See the METADATA header. */
  | 'forbidden_metadata_key';

export type TopupDecision =
  | {
      credit: true;
      practiceId: string;
      /** Who clicked, for the audit row. Absent is legal: the credit is the
       *  practice's, and `logAudit` records an unattributed user honestly. */
      userId: string | null;
      amountMicroUsd: bigint;
      amountTotalCents: number;
      /** GLOBALLY unique in `ledger_entries`. See {@link topupIdempotencyKey}. */
      idempotencyKey: string;
      note: string;
    }
  | { credit: false; reason: TopupRefusal; detail: string };

/**
 * THE IDEMPOTENCY KEY IS THE **SESSION** ID, NOT THE EVENT ID.
 *
 * ⚠️ AND THAT DISTINCTION IS THE DIFFERENCE BETWEEN ONE CREDIT AND TWO. Stripe
 * retries a failed delivery with the SAME event id, so an event-keyed row is
 * idempotent against retries — but a single Checkout Session can produce more
 * than one event (`checkout.session.completed`, then
 * `checkout.session.async_payment_succeeded` for a delayed method), and those
 * carry DIFFERENT event ids. An event-keyed row would credit that session twice.
 *
 * Keying on the session makes "this session credited at most once" true
 * regardless of how many events describe it, and regardless of which types a
 * future step subscribes to.
 *
 * ⚠️ AND IT IS ENFORCED BY THE UNIQUE INDEX, NOT BY A CHECK-THEN-WRITE. B5 gave
 * `ledger_entries.idempotencyKey` a GLOBAL unique for this: a duplicate is
 * refused by the database rather than by a read that another request can race.
 * On an append-only table a double credit can never be deleted — only offset by
 * an `adjustment` row that both then live beside forever.
 */
export function topupIdempotencyKey(sessionId: string): string {
  return `topup:stripe_session:${sessionId}`;
}

/** Cents → micro-dollars. Integer throughout: GATE 0.4 forbids float anywhere
 *  near money, and `1e-6 USD` per micro-dollar makes one cent exactly 10 000.
 *  Takes a `number` because that is what Stripe's JSON carries, and converts
 *  through `BigInt` only after the integrality check in {@link decideTopup}. */
export function centsToMicroUsd(cents: number): bigint {
  return BigInt(cents) * 10_000n;
}

/** The event types this handler acts on. A type outside this set is refused
 *  with `unhandled_event_type` and a 200 — see the route's header for why a
 *  refusal is still a 200 to Stripe. */
export const HANDLED_EVENT_TYPES: readonly string[] = ['checkout.session.completed'];

/**
 * DECIDE WHETHER AN EVENT MAY CREDIT A PRACTICE'S WALLET, AND BY HOW MUCH.
 *
 * PURE. Every refusal is named rather than collapsed into a boolean, because
 * B9 has to reconcile this ledger against Stripe's own record and "we received
 * an event and wrote nothing" is only auditable if the reason survives.
 *
 * ⚠️ THE ORDER OF THE CHECKS IS DELIBERATE. Mode is checked BEFORE anything is
 * read out of the payload, so a test-mode event pointed at production is
 * refused without this code ever forming an opinion about its amount. That
 * ordering costs nothing and makes the guardrail the first thing a reader sees.
 */
export function decideTopup(event: CheckoutEventShape, db: DbIdentity): TopupDecision {
  const refuse = (reason: TopupRefusal, detail: string): TopupDecision => ({
    credit: false,
    reason,
    detail,
  });

  if (!HANDLED_EVENT_TYPES.includes(event.type)) {
    return refuse('unhandled_event_type', `event type "${event.type}" is not handled`);
  }

  // ── MODE. Two positive confirmations, never one and its negation. ─────────
  const isProd = checkProdDb(db.database, db.host).ok;
  const isNonProd = checkNonProdDb(db.database, db.host).ok;
  if (!isProd && !isNonProd) {
    return refuse(
      'undeterminable_environment',
      `database "${db.database}" is confirmed neither production nor non-production — ` +
        `refusing to credit money into a ledger whose identity is unknown`,
    );
  }
  if (isProd !== event.livemode) {
    return refuse(
      'mode_mismatch',
      isProd
        ? 'a TEST-mode Stripe event may not credit the PRODUCTION ledger — nobody paid for it'
        : 'a LIVE-mode Stripe event may not credit a NON-PRODUCTION ledger — the record would be lost',
    );
  }

  const session = event.data.object;

  // ── METADATA. Allowlist, and the practice must be named. ─────────────────
  const metadata = session.metadata ?? {};
  const stray = Object.keys(metadata).filter((k) => !ALLOWED_METADATA_KEYS.includes(k));
  if (stray.length > 0) {
    return refuse(
      'forbidden_metadata_key',
      `metadata carries ${stray.length} key(s) outside the allowlist: ${stray.join(', ')} — ` +
        `see DISCOVERY §E.5, a visit id dereferences to a named patient in one hop`,
    );
  }
  const practiceId = metadata.practiceId?.trim();
  if (!practiceId) {
    return refuse('no_practice_in_metadata', 'no practiceId in session metadata — nothing to credit');
  }

  // ── THE MONEY. ───────────────────────────────────────────────────────────
  if (session.payment_status !== 'paid') {
    return refuse(
      'not_paid',
      `payment_status is "${session.payment_status}" — only a settled session credits`,
    );
  }
  if (session.currency?.toLowerCase() !== 'usd') {
    return refuse(
      'currency_not_usd',
      `currency is "${session.currency}" — the micro-dollar conversion is USD-only and is not guessed`,
    );
  }
  const cents = session.amount_total;
  if (cents === null || !Number.isSafeInteger(cents) || cents <= 0) {
    return refuse(
      'amount_not_creditable',
      `amount_total is ${cents} — a credit must be a positive whole number of cents ` +
        `(ledger_entries_kind_sign CHECKs topup > 0)`,
    );
  }

  return {
    credit: true,
    practiceId,
    userId: metadata.userId?.trim() || null,
    amountMicroUsd: centsToMicroUsd(cents),
    amountTotalCents: cents,
    idempotencyKey: topupIdempotencyKey(session.id),
    // PHI-free by construction: two Stripe ids and an integer. No email, no
    // name, no line-item description — Stripe's own record holds those and this
    // note exists so B9 can join the two without dereferencing anything.
    note: `stripe_session=${session.id} stripe_event=${event.id} cents=${cents}`,
  };
}
