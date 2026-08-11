'use client';

// ============================================================================
// FOUNDATION B7 STEP 2 — THE DOOR. Settings → Billing → Add credit.
// ----------------------------------------------------------------------------
// RELAY B7 step 1 recorded what was missing: "there is no way to CREATE a
// Checkout Session yet — that is B7 step 2, along with the settings-page door
// (`settings/page.tsx:895-905` still carries the disabled placeholder)."
//
// This is that door. It is a thin thing on purpose: it renders the offered
// denominations, POSTs one of them to `/api/stripe/checkout`, and follows the
// hosted URL the server hands back. It knows no key, decides no amount that is
// not in the shared constant, and never sees a card.
//
// ⚠️ IT DOES NOT DECIDE WHETHER IT SHOULD EXIST. `settings/page.tsx` renders it
// only when a Stripe secret key is present in the environment — see the comment
// at that call site for why "present" and not "valid".
//
// ⚠️ AND IT SENDS ONLY AN AMOUNT. There is no practice or user field here, and
// there must never be one: the server reads both off the session, which is what
// makes step 1's metadata allowlist a guarantee rather than a hope
// (`lib/billing/stripe-checkout.ts` header (a)).
// ============================================================================

import { useState } from 'react';

import {
  TOPUP_DENOMINATIONS_CENTS,
  formatCentsUsd,
} from '@/lib/billing/stripe-checkout';

export function BillingTopupPanel() {
  const [pending, setPending] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function startCheckout(amountCents: number) {
    setError(null);
    setPending(amountCents);
    try {
      const res = await fetch('/api/stripe/checkout', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ amountCents }),
      });
      const body: unknown = await res.json().catch(() => null);

      if (!res.ok) {
        // The server names its refusals. Show the name rather than inventing a
        // friendlier sentence that hides which guard fired — this surface is
        // reachable only by an authenticated member of the practice.
        const reason =
          typeof body === 'object' && body !== null && 'error' in body
            ? String((body as { error: unknown }).error)
            : `http_${res.status}`;
        setError(reason);
        setPending(null);
        return;
      }

      const url =
        typeof body === 'object' && body !== null && 'url' in body
          ? (body as { url: unknown }).url
          : null;
      if (typeof url !== 'string' || !url) {
        setError('no_checkout_url');
        setPending(null);
        return;
      }

      // Leave for Stripe. No PAN ever reaches this system (SPEC §2.3).
      window.location.assign(url);
    } catch {
      setError('network_error');
      setPending(null);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {TOPUP_DENOMINATIONS_CENTS.map((cents) => (
          <button
            key={cents}
            type="button"
            className="qm-lin-btn"
            disabled={pending !== null}
            onClick={() => void startCheckout(cents)}
            style={pending !== null ? { opacity: 0.45, cursor: 'progress' } : undefined}
          >
            {pending === cents ? 'Opening…' : `Add ${formatCentsUsd(cents)}`}
          </button>
        ))}
      </div>
      {error && (
        // ⚠️ THE HOUSE ERROR SHAPE, COPIED FROM `profile-form.tsx`, AND BOTH
        // HALVES OF IT MATTER. The first draft invented `--color-linear-red`,
        // which is undeclared — an undeclared token falls to `transparent` with
        // no error, so the message would simply not have been there. The second
        // reached for `--color-linear-danger`, which IS declared and bridges to
        // `--rounds-critical` at 3.33:1 — below AA on a Rounds surface.
        //
        // `gate-rounds-bridge.test.ts` caught both, in that order, and it
        // derives its foreground set FROM USAGE: writing `color:
        // var(--color-linear-danger)` anywhere is what put that name in scope.
        // `--color-linear-coral` + `qm-rounds-error` is the established pair,
        // and the class is what lets the Rounds host own the treatment instead
        // of this caller.
        <p
          role="alert"
          className="qm-rounds-error"
          style={{
            margin: 0,
            fontFamily: 'var(--font-sans)',
            fontSize: 12,
            color: 'var(--color-linear-coral)',
          }}
        >
          Checkout unavailable — {error}
        </p>
      )}
    </div>
  );
}
