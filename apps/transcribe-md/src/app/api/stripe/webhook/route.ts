// ============================================================================
// FOUNDATION B7 — THE STRIPE WEBHOOK. HOSTED CHECKOUT TOP-UPS.
// ----------------------------------------------------------------------------
// RELAY B7's gate, clause by clause:
//
//   "signature verification is the FIRST statement in the handler"
//   "`req.text()` before anything, never `req.json()`"
//   "the webhook passes `userId` and `practiceId` explicitly; it has no session"
//   "the ADMIN_*/CHECKOUT_* audit labels ship as a Prisma enum migration"
//
// ⚠️ THIS ROUTE IS UNAUTHENTICATED BY DESIGN AND REACHABLE FROM THE INTERNET
// THE MOMENT IT EXISTS. DISCOVERY §E.4 measured it: `proxy.ts:21-26` matches
// only `/dashboard/:path*`, `/visits/:path*` and `/settings/:path*`, so nothing
// gates this path, and `Caddyfile:116-124` passes all of `app.quillmd.com`
// through without path filtering. That is CORRECT — the signature IS the auth —
// and it is precisely why the ordering below is not a style preference.
//
// ============================================================================
// THE ORDER, AND WHY EACH STEP IS WHERE IT IS
// ----------------------------------------------------------------------------
//   1. Is a webhook secret configured?   No → 503. Nothing else runs.
//   2. Is there a `stripe-signature`?    No → 400. Nothing else runs.
//   3. Read the RAW body — `req.text()`.
//   4. VERIFY. Fails → 400.
//   ─────────── only past this line may anything touch the database ──────────
//   5. Decide (pure), then write.
//
// ⚠️ STEP 1 IS THE FAIL-CLOSED ARM AND IT IS THE REASON THIS CAN SHIP TO
// PRODUCTION AHEAD OF ANY STRIPE ACCOUNT. With `STRIPE_WEBHOOK_SECRET` unset —
// which is its state in every environment today — every request is refused
// before the body is even read. A route that is inert until a secret exists is
// a route whose blast radius is a config change somebody makes deliberately.
//
// ⚠️ STEP 3 DELIBERATELY BREAKS THIS REPO'S CONVENTION, AND THE BREAK IS THE
// POINT. DISCOVERY §E.3: ten-plus routes here call `await req.json()`, and a Web
// `Request` body is a SINGLE-USE STREAM. `JSON.stringify(await req.json())` is
// not byte-identical to what Stripe signed — key order, whitespace and unicode
// escaping all differ — so a `req.json()` here fails as an opaque SIGNATURE
// error rather than a parse error, and reads as a wrong secret. Next's own
// bundled docs (`route.md:566`) show `await request.text()` for exactly this.
// No `bodyParser` config is needed or supported under the App Router.
//
// ============================================================================
// ⚠️ NOTHING BEFORE THE SIGNATURE CHECK WRITES AN AUDIT ROW, AND THAT IS A
// DECISION RATHER THAN AN OVERSIGHT
// ----------------------------------------------------------------------------
// The instinct — and this repo's own canon for gates — is "and the refusal is
// audited". It is the wrong instinct HERE, and only here, because this endpoint
// is unauthenticated: an audit row written per unverified request is a write
// amplification whose rate an anonymous caller chooses. `audit_logs` is the
// §164.312(b) record of PHI access, and letting the open internet append to it
// is a worse outcome than losing the signal.
//
// So the invariant is stated positively and is what the gate asserts:
//
//     NOTHING TOUCHES THE DATABASE UNTIL THE SIGNATURE HAS VERIFIED.
//
// A forged or unsigned request is refused, counted in the application log, and
// leaves no row. Every refusal that IS audited below happened AFTER a valid
// Stripe signature, so its rate is bounded by Stripe's own retry policy rather
// than by an attacker. Adding the pre-verification audit row later is a pure
// addition if the trade is ever re-judged — the reversible direction.
//
// ============================================================================
// ⚠️ WHY A REFUSAL IS STILL HTTP 200
// ----------------------------------------------------------------------------
// Stripe retries any non-2xx with backoff for up to three days. A refusal that
// will NEVER succeed on retry — an unhandled event type, a mode mismatch, a
// session with no practice — must therefore be acknowledged, or it becomes an
// endless redelivery of a decision that is already final and already recorded.
//
// 4xx/5xx is reserved for "ask us again": the secret is missing (503), the
// signature is absent or wrong (400 — a retry with the same body will fail
// identically, and that is the one case where refusing to acknowledge is worth
// the noise because it is a live misconfiguration somebody must see), and an
// unexpected write failure (500 — a retry genuinely might land).
// ============================================================================

import Stripe from 'stripe';

import prisma from '@meddoc/db';
import { describeDbTarget } from '@meddoc/db/guard';

import { logAudit } from '@/lib/audit';
import { decideTopup, type CheckoutEventShape } from '@/lib/billing/stripe-topup';

export const runtime = 'nodejs';
/** Never cached, never statically evaluated: every request carries a distinct
 *  signature over a distinct body. */
export const dynamic = 'force-dynamic';

/** Prisma's unique-violation code. The idempotency key's GLOBAL unique index is
 *  what makes a redelivery a no-op, so this is the SUCCESS path for a duplicate,
 *  not an error path. */
const PRISMA_UNIQUE_VIOLATION = 'P2002';
/** Prisma's FK-violation code — a `practiceId` that names no practice. */
const PRISMA_FK_VIOLATION = 'P2003';

function prismaCode(e: unknown): string | null {
  return typeof e === 'object' && e !== null && 'code' in e
    ? String((e as { code: unknown }).code)
    : null;
}

export async function POST(req: Request): Promise<Response> {
  // ── 1. FAIL CLOSED ON AN UNCONFIGURED ENDPOINT. ──────────────────────────
  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!webhookSecret) {
    console.warn('[stripe-webhook] refused: STRIPE_WEBHOOK_SECRET is not configured');
    return new Response('stripe webhook is not configured', { status: 503 });
  }

  // ── 2. NO SIGNATURE HEADER — not a Stripe delivery at all. ───────────────
  const signature = req.headers.get('stripe-signature');
  if (!signature) {
    return new Response('missing stripe-signature', { status: 400 });
  }

  // ── 3. THE RAW BODY. `text()`, never `json()`. See the header. ───────────
  const rawBody = await req.text();

  // ── 4. VERIFY. Everything below this line is trusted; nothing above it
  //       has touched the database. ─────────────────────────────────────────
  let event: Stripe.Event;
  try {
    // `constructEvent` is the SYNC verifier and is safe here because this route
    // declares `runtime = 'nodejs'` — DISCOVERY §E.3. It checks the timestamp
    // tolerance (replay) and compares in constant time; both are the reason
    // this is the SDK's job and not a hand-rolled HMAC.
    event = Stripe.webhooks.constructEvent(rawBody, signature, webhookSecret);
  } catch (err) {
    console.warn(
      `[stripe-webhook] signature verification FAILED: ${
        err instanceof Error ? err.message : 'unknown'
      }`,
    );
    return new Response('signature verification failed', { status: 400 });
  }

  // ── 5. DECIDE. Pure — see `lib/billing/stripe-topup.ts`. ─────────────────
  // ⚠️ The database IDENTITY is passed in rather than read inside the decision,
  // so the mode rule is provable from a literal. `DATABASE_URL` is parsed here
  // and nowhere else in this path.
  let dbIdentity: { database: string; host?: string };
  try {
    const t = describeDbTarget(process.env.DATABASE_URL ?? '');
    dbIdentity = { database: t.database, host: t.host };
  } catch {
    // Unparseable or unset. `decideTopup` refuses an unidentifiable environment
    // by design (`undeterminable_environment`) — an empty name reaches that
    // branch rather than throwing here.
    dbIdentity = { database: '' };
  }

  const decision = decideTopup(event as unknown as CheckoutEventShape, dbIdentity);

  if (!decision.credit) {
    // ⚠️ EXPLICIT `userId` AND `practiceId` — this handler has NO SESSION, and
    // `logAudit` calls `auth()` internally when either is missing (§E.6). Both
    // are genuinely unknown on most refusal paths, and `null` is the honest
    // value: the row lands with `practiceIdSnapshot = 'UNATTRIBUTED'`, which is
    // distinguishable from a wrongly-attributed one.
    void logAudit({
      action: 'CHECKOUT_TOPUP_REFUSED',
      targetType: 'stripe_event',
      targetId: event.id,
      success: false,
      errorCode: decision.reason,
      userId: null,
      practiceId: null,
      metadata: {
        reason: decision.reason,
        detail: decision.detail,
        eventType: event.type,
        livemode: event.livemode,
      },
    });
    return new Response(JSON.stringify({ received: true, credited: false }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  }

  // ── 6. WRITE. One append-only row. ───────────────────────────────────────
  try {
    const created = await prisma.ledgerEntry.create({
      data: {
        practiceId: decision.practiceId,
        // Derived by the trigger and overwritten unconditionally — sent only
        // because Prisma's generated type requires it. B6 recorded this as a
        // seam defect (`practiceIdSnapshot` has no `@default`, unlike
        // `balanceAfter`/`seq`); both fields read the SAME variable here, so
        // the pair cannot drift.
        practiceIdSnapshot: decision.practiceId,
        // SPEC §2.4 — two separate running balances. A purchase credits `paid`;
        // the `$10` promo grant credits `promo` and is a later B7 step.
        bucket: 'paid',
        kind: 'topup',
        // POSITIVE. `ledger_entries_kind_sign` CHECKs `topup > 0` — the balance
        // is a running sum, so money arriving is a positive amount.
        amountMicroUsd: decision.amountMicroUsd,
        idempotencyKey: decision.idempotencyKey,
        note: decision.note,
        // ⚠️ `pricing` STAYS NULL, AND THE CHECK PERMITS THAT DELIBERATELY.
        // `ledger_entries_usage_has_pricing` is CONDITIONAL —
        // `kind <> 'usage' OR pricing IS NOT NULL` — because ruling 90(d) says
        // a top-up is money ARRIVING, not money computed. Inventing a pricing
        // object for one would be a claim nobody made.
      },
      select: { id: true, balanceAfter: true, seq: true },
    });

    void logAudit({
      action: 'CHECKOUT_TOPUP_CREDITED',
      targetType: 'ledger_entry',
      targetId: created.id,
      userId: decision.userId,
      practiceId: decision.practiceId,
      metadata: {
        stripeEventId: event.id,
        amountMicroUsd: decision.amountMicroUsd.toString(),
        amountTotalCents: decision.amountTotalCents,
        bucket: 'paid',
        // The DATABASE's arithmetic, read back from the row it derived — not
        // the caller's opinion of what the balance now is (ruling 89(d)).
        balanceAfter: created.balanceAfter.toString(),
        seq: created.seq.toString(),
      },
    });

    return new Response(JSON.stringify({ received: true, credited: true }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  } catch (err) {
    const code = prismaCode(err);

    // A REDELIVERY. The unique index did its job; this is not an error.
    if (code === PRISMA_UNIQUE_VIOLATION) {
      void logAudit({
        action: 'CHECKOUT_TOPUP_DUPLICATE',
        targetType: 'stripe_event',
        targetId: event.id,
        userId: decision.userId,
        practiceId: decision.practiceId,
        metadata: { idempotencyKey: decision.idempotencyKey, stripeEventId: event.id },
      });
      return new Response(JSON.stringify({ received: true, credited: false, duplicate: true }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      });
    }

    // A practice that does not exist. Retrying cannot fix it, so acknowledge.
    if (code === PRISMA_FK_VIOLATION) {
      void logAudit({
        action: 'CHECKOUT_TOPUP_REFUSED',
        targetType: 'stripe_event',
        targetId: event.id,
        success: false,
        errorCode: 'unknown_practice',
        userId: decision.userId,
        practiceId: null,
        metadata: { reason: 'unknown_practice', claimedPracticeId: decision.practiceId },
      });
      return new Response(JSON.stringify({ received: true, credited: false }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      });
    }

    // Anything else genuinely might succeed on a retry — let Stripe redeliver.
    // ⚠️ No audit row here: the write failed for an unknown reason, and the
    // redelivery will produce one when it lands. Recording a refusal we do not
    // understand would put a claim in the audit trail that nothing verified.
    console.error('[stripe-webhook] ledger write failed', err);
    return new Response('ledger write failed', { status: 500 });
  }
}
