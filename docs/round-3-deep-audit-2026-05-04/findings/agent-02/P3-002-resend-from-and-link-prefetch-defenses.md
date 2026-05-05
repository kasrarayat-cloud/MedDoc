---
id: A02-P3-002
severity: P3
title: Polish — RESEND_API_KEY presence, not RESEND_FROM_VERIFIED, gates production token-email sends; auto-confirm warn includes full email
domain: Auth & session security
files:
  - apps/transcribe-md/src/app/api/auth/forgot-password/route.ts:92
  - apps/transcribe-md/src/app/api/auth/resend-verification/route.ts:84
  - apps/transcribe-md/src/actions/auth.ts:360
---

## Issue

Two small posture items observed during the auth read-through.

**1. Email-send branching.** Every email-related route checks
`process.env.RESEND_API_KEY` directly to decide whether to send vs
log the token URL:

```ts
// forgot-password/route.ts:92
if (process.env.RESEND_API_KEY) {
  await sendPasswordResetEmail({ ... });
} else {
  console.warn(`[auth:forgot-password] RESEND_API_KEY unset — ... dev-only link: ${resetUrl}`);
}
```

The codebase already has the more-correct gate
`isEmailDeliveryEnabled()` (in
`apps/transcribe-md/src/lib/email-enabled.ts`):
```ts
export function isEmailDeliveryEnabled(): boolean {
  return (
    !!process.env.RESEND_API_KEY &&
    process.env.RESEND_FROM_VERIFIED === 'true'
  );
}
```
…which adds the "and the from-domain has been verified at Resend"
check. The login + signup paths use `isEmailDeliveryEnabled()`
already. The forgot-password / resend-verification / change-email
routes are inconsistent — they only check `RESEND_API_KEY`, not the
verified-domain flag.

Concretely: an env that has `RESEND_API_KEY` set but
`RESEND_FROM_VERIFIED=false` (or unset) will *attempt* to email,
and either Resend returns 403 (DNS not verified) or the mail goes
out from a half-configured "@onboarding.resend.dev" sandbox
sender that lands in spam. Either way the user-visible result is
"my reset email never arrived."

**2. Auto-confirm log line is over-detailed.**
`apps/transcribe-md/src/actions/auth.ts:360-362`:
```ts
if (autoConfirm) {
  console.warn(
    `[QA-BYPASS] auto-confirmed email for ${emailLower} (domain on EMAIL_AUTO_CONFIRM_DOMAINS allowlist)`
  );
}
```
The full email address is logged. If the bypass mechanism stays in
place (separate finding A02-P0-001 recommends taking it off prod
entirely), the log line should at most carry the *domain*, not the
full address — that's the redactPhi pattern used elsewhere in
this same file's catch handlers (e.g.,
`apps/transcribe-md/src/app/api/auth/forgot-password/route.ts:117`
uses `redactPhi(...)` for the same reason).

## Evidence

`apps/transcribe-md/src/lib/email-enabled.ts:22-27`:
```ts
export function isEmailDeliveryEnabled(): boolean {
  return (
    !!process.env.RESEND_API_KEY &&
    process.env.RESEND_FROM_VERIFIED === 'true'
  );
}
```

Inconsistent users:
- `forgot-password/route.ts:92` — uses raw `process.env.RESEND_API_KEY`
- `resend-verification/route.ts:84` — uses raw `process.env.RESEND_API_KEY`
- `confirm-email/route.ts:129` — uses raw `process.env.RESEND_API_KEY`
- `change-email/route.ts:137` — uses raw `process.env.RESEND_API_KEY`

vs. correct call-sites:
- `auth.ts:132` (login pre-check) — `isEmailDeliveryEnabled()`
- `auth.ts:364` (signup verify gate) — `isEmailDeliveryEnabled()`

## Risk

Both items are polish — the email gating inconsistency causes UX
friction in the "domain not verified" misconfiguration window
rather than a security exposure, and the log-line detail is a
defense-in-depth concern, not an active leak.

## Recommended fix

1. Replace `if (process.env.RESEND_API_KEY)` with
   `if (isEmailDeliveryEnabled())` in the four routes listed above.
   Single import, one-line change per file.

2. Demote the `[QA-BYPASS]` log line to:
   ```ts
   console.warn(
     `[QA-BYPASS] auto-confirmed signup for domain ${emailLower.split('@')[1]} (allowlist)`
   );
   ```
   Keeps the operator-visible signal, drops the local-part PII.
