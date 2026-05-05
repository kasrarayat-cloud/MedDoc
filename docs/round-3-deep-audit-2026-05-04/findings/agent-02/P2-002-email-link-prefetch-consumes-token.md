---
id: A02-P2-002
severity: P2
title: Email-verification and email-change confirm endpoints use GET — corporate link-scanning prefetch consumes the single-use token before the user clicks
domain: Auth & session security
files:
  - apps/transcribe-md/src/app/api/auth/verify-email/route.ts:43
  - apps/transcribe-md/src/app/api/auth/confirm-email/route.ts:51
  - apps/transcribe-md/src/lib/auth-tokens.ts:105
---

## Issue

Both email-side state-mutation endpoints accept the token via GET
query-string, and both are atomic single-use:

```ts
// verify-email/route.ts:43-78
export const GET = withApiHandler('api:auth:verify-email', async (req) => {
  ...
  const token = url.searchParams.get('token');
  ...
  const consumed = await consumeAuthToken({ token, purpose: EMAIL_VERIFICATION });
  if (!consumed) return redirectToLogin('invalid-or-expired');
  await prisma.user.update({ ... emailVerified: new Date() });
  ...
});
```

```ts
// auth-tokens.ts:127-132 — atomic single-use
const updated = await prisma.authToken.updateMany({
  where: { id: row.id, usedAt: null },
  data: { usedAt: new Date() },
});
```

Many corporate email security gateways (Mimecast, Proofpoint URL
Defense, Microsoft Defender SafeLinks, Google's Workspace link
scanning) **prefetch every URL** in inbound mail to render a
sandboxed render or a malware verdict. Because the token is `used`
on the *first* GET — including the security scanner's GET — the
legit user's subsequent click lands on `redirectToLogin('invalid-or-expired')`.

The same shape applies at `confirm-email/route.ts` for the
EMAIL_CHANGE flow; the `redirectToSettings('invalid-or-expired')`
path replaces the user-facing OK with a frustrating "your link
already expired" toast even though the user clicked within seconds.

## Evidence

`apps/transcribe-md/src/lib/auth-tokens.ts:105-135`:
```ts
export async function consumeAuthToken(args): Promise<...> {
  if (!args.token || args.token.length < 20) return null;
  const tokenHash = hashToken(args.token);
  const row = await prisma.authToken.findUnique({ where: { tokenHash }, ... });
  if (!row) return null;
  if (row.purpose !== args.purpose) return null;
  if (row.usedAt !== null) return null;
  if (row.expiresAt < new Date()) return null;

  // Atomic consume — second concurrent call gets count=0.
  const updated = await prisma.authToken.updateMany({
    where: { id: row.id, usedAt: null },
    data: { usedAt: new Date() },
  });
  if (updated.count === 0) return null;

  return { id: row.id, userId: row.userId, metadata: row.metadata };
}
```

The route handlers are GET, not POST, so there is no human-click
gate before consumption:
- `verify-email/route.ts:43` — `export const GET = ...`
- `confirm-email/route.ts:51` — `export const GET = ...`

Comment in `confirm-email/route.ts:21-24` acknowledges the choice:
```
// GET instead of POST because the browser is following a link from
// an email — POST-via-link needs JS. The token itself is single-use
// and high-entropy, so read-only-GET-side-effects is OK here.
```

The reasoning is correct on the security front (high-entropy +
single-use defends against guessing) but doesn't address the link-
prefetch UX failure mode.

## Risk

Pilot doctors using a corporate Outlook/Google Workspace mailbox
will hit this on a meaningful fraction of signups. The user-facing
symptom is "your verification link is invalid or has expired" on
the first click — they re-request a token, click, possibly hit it
again. Three rounds of friction at the very first touch with the
product is a churn vector.

For email-change specifically, hitting the prefetch-eats-token
path at `confirm-email/route.ts:66` shows a particularly
unhelpful redirect to `/settings?emailChange=invalid-or-expired`
without an obvious "try again" button.

This is *primarily* a UX failure but it is also a soft-DoS the
attacker doesn't even need to launch — the user's own email
provider triggers it.

## Recommended fix

The standard pattern is a two-step click-through:

1. The email link points to a *page* (`/verify-email?token=...`)
   that renders a "Click to confirm your email" button. Loading
   the page does not consume the token.
2. The button POSTs to `/api/auth/verify-email`, which performs
   the consume. Email scanners GET the page, rendering safely.

Same approach for `/confirm-email`. The page can include a JS
auto-click for users with JS enabled if the runbook authors want
to keep the one-tap UX, since security scanners typically render
without executing scripts.

A lighter-weight alternative: keep the GET endpoint, but treat
the *first* GET from a known-prefetcher User-Agent (or any GET
whose `Sec-Purpose: prefetch` / `Purpose: prefetch` header is
present) as a soft-touch that does NOT consume — only logs the
hit. The legit user's second click without those signals
consumes. Less robust than the page-then-POST approach but
cheaper to ship.
