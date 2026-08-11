// ============================================================================
// FOUNDATION B7 STEP 2 — CREATE A HOSTED CHECKOUT SESSION
// ----------------------------------------------------------------------------
// The outbound half of B7. Step 1's webhook credits a wallet when Stripe says a
// session was paid; this is the only thing in the system that may ask Stripe to
// take money in the first place.
//
// SPEC §2.3: "Stripe Checkout only. No PAN ever reaches this system." That is
// literal — this route returns a Stripe-hosted URL and the browser leaves. No
// card field is ever rendered by us, and no publishable key is needed, which is
// what DISCOVERY §E.7's build-arg inlining trap is avoided by.
//
// ============================================================================
// ⚠️ THIS ROUTE IS AUTHENTICATED, AND THAT INVERTS ONE OF STEP 1's DECISIONS
// ----------------------------------------------------------------------------
// The webhook is unauthenticated by design (the signature IS the auth), so
// ruling 91(b) deliberately writes NO audit row before verification: an
// anonymous caller would otherwise choose the append rate into `audit_logs`.
//
// Here the opposite holds. Every refusal below happens AFTER `getSession()` and
// AFTER the rate limiter, so its rate is bounded by a logged-in user's budget.
// A refusal that is not audited here is simply a lost signal, so every one is
// audited — this repo's ordinary canon, applied because the reason to suspend it
// is absent.
//
// ============================================================================
// THE ORDER, AND WHY EACH STEP IS WHERE IT IS
// ----------------------------------------------------------------------------
//   1. AUTHENTICATE.  No session → 401. Nothing else runs.
//   2. RATE LIMIT, per user.
//   3. Read the body for ONE value: `amountCents`.
//   4. Decide (pure) — configuration, mode, the practice, the amount.
//   5. Only on `create: true` does anything reach Stripe.
//
// ⚠️ STEP 4 IS WHERE THE PAYING PARTY IS FIXED, AND IT COMES FROM STEP 1 OF THIS
// LIST, NOT FROM STEP 3. `practiceId` and `userId` are read off the session and
// handed to `decideCheckout`; the body contributes an amount and nothing else.
// `lib/billing/stripe-checkout.ts` header (a) explains why that is what makes
// step 1's metadata allowlist mean anything at all.
//
// ⚠️ AND THE RETURN URLS ARE SERVER CONSTANTS, NOT THE REQUEST'S ORIGIN. A
// `Host` header is caller-controlled; deriving `success_url` from it would let
// somebody hand a doctor a Stripe page that returns them to a site of the
// caller's choosing with a paid session behind them. `APP_URL` is baked at
// image-build time and is the same value the rest of the app links with.
// ============================================================================

import { NextResponse } from 'next/server';
import Stripe from 'stripe';

import { describeDbTarget } from '@meddoc/db/guard';

import { apiError, withApiHandler } from '@/lib/api-error';
import { getSession } from '@/lib/auth';
import { logAudit } from '@/lib/audit';
import { APP_URL } from '@/lib/constants';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { classifyStripeSecretKey, decideCheckout } from '@/lib/billing/stripe-checkout';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export const POST = withApiHandler(
  'api:stripe:checkout',
  async (req) => {
    // ── 1. AUTHENTICATE. ───────────────────────────────────────────────────
    const session = await getSession();
    const userId = session?.user.id;
    if (!userId) return apiError('unauthorized', 401);

    // ── 2. RATE LIMIT. Money-adjacent and per-user. ────────────────────────
    const blocked = rateLimitOr429(RATE_LIMITS.VISIT_OPS, userId);
    if (blocked) return blocked;

    // ── 3. THE BODY, AND ONLY ONE VALUE OUT OF IT. ────────────────────────
    // A malformed body is not an error worth distinguishing: `amountCents`
    // becomes `undefined` and the decision refuses it by name.
    let amountCents: unknown;
    try {
      const body: unknown = await req.json();
      amountCents =
        typeof body === 'object' && body !== null
          ? (body as { amountCents?: unknown }).amountCents
          : undefined;
    } catch {
      amountCents = undefined;
    }

    // ── 4. DECIDE. Pure — see `lib/billing/stripe-checkout.ts`. ────────────
    const secretKey = process.env.STRIPE_SECRET_KEY;
    const keyMode = classifyStripeSecretKey(secretKey);

    let dbIdentity: { database: string; host?: string };
    try {
      const t = describeDbTarget(process.env.DATABASE_URL ?? '');
      dbIdentity = { database: t.database, host: t.host };
    } catch {
      // Unparseable or unset reaches `undeterminable_environment` by design,
      // rather than throwing here — the same handling step 1's route uses.
      dbIdentity = { database: '' };
    }

    const decision = decideCheckout(
      { practiceId: session.user.practiceId, userId, amountCents },
      dbIdentity,
      keyMode,
    );

    if (!decision.create) {
      void logAudit({
        action: 'CHECKOUT_SESSION_REFUSED',
        targetType: 'practice',
        targetId: session.user.practiceId ?? 'UNATTRIBUTED',
        success: false,
        errorCode: decision.reason,
        userId,
        practiceId: session.user.practiceId ?? null,
        metadata: {
          reason: decision.reason,
          detail: decision.detail,
          // The MODE, never the key. A classification is safe to record; the
          // credential it was derived from is not.
          keyMode,
          requestedAmountCents:
            typeof amountCents === 'number' ? amountCents : String(amountCents),
        },
      });

      // `not_configured` is the fail-closed arm and is the state of every
      // environment today — it is a 503 for the same reason the webhook's is:
      // the route exists and refused before doing any work, and a 503 says
      // "not available" rather than "you asked wrongly".
      const status = decision.reason === 'not_configured' ? 503 : 400;
      return NextResponse.json(
        { error: decision.reason, detail: decision.detail },
        { status },
      );
    }

    // ── 5. ASK STRIPE. The first and only network call in this file. ───────
    // Non-null asserted by construction: `decideCheckout` refuses `absent` and
    // `unrecognised` above, and both are the only classifications an empty or
    // unusable key can take.
    const stripe = new Stripe(secretKey as string);

    let checkoutUrl: string | null;
    let checkoutSessionId: string;
    try {
      const created = await stripe.checkout.sessions.create({
        mode: 'payment',
        // ⚠️ The metadata is the decision's, verbatim — built from the session
        // and checked against step 1's `ALLOWED_METADATA_KEYS`. Nothing is
        // added here, because a key added at the call site is exactly the
        // regression that guard exists to catch.
        metadata: decision.metadata,
        line_items: [
          {
            quantity: 1,
            price_data: {
              currency: 'usd',
              unit_amount: decision.amountCents,
              product_data: { name: decision.productName },
            },
          },
        ],
        success_url: `${APP_URL}/settings?topup=success#billing`,
        cancel_url: `${APP_URL}/settings?topup=cancelled#billing`,
      });
      checkoutUrl = created.url;
      checkoutSessionId = created.id;
    } catch (err) {
      // A vendor failure. Nothing was charged and nothing was written; the
      // doctor sees a retryable error.
      console.error('[stripe-checkout] session creation failed', err);
      void logAudit({
        action: 'CHECKOUT_SESSION_REFUSED',
        targetType: 'practice',
        targetId: decision.practiceId,
        success: false,
        errorCode: 'stripe_call_failed',
        userId,
        practiceId: decision.practiceId,
        metadata: { reason: 'stripe_call_failed', keyMode },
      });
      return apiError('could not start checkout', 502);
    }

    void logAudit({
      action: 'CHECKOUT_SESSION_CREATED',
      targetType: 'stripe_session',
      targetId: checkoutSessionId,
      userId,
      practiceId: decision.practiceId,
      metadata: {
        // ⚠️ The SESSION id is recorded because it is the idempotency key step 1
        // derives its ledger row from (`topupIdempotencyKey`). This row and that
        // row therefore join without either side dereferencing anything else,
        // which is what B9's reconciliation needs.
        stripeSessionId: checkoutSessionId,
        amountCents: decision.amountCents,
        bucket: 'paid',
      },
    });

    return NextResponse.json({ url: checkoutUrl });
  },
);
