---
id: A02-P1-001
severity: P1
title: signupAction returns a distinct error when the email is already registered — full account enumeration vector
domain: Auth & session security
files:
  - apps/transcribe-md/src/actions/auth.ts:325
  - apps/transcribe-md/src/actions/auth.ts:329
---

## Issue

The signup server-action does an *up-front* uniqueness probe and
returns a UI-distinct error message when the email is already taken:

```ts
const existing = await prisma.user.findUnique({
  where: { email: emailLower },
  select: { id: true },
});
if (existing) {
  return {
    ok: false,
    errors: { email: 'An account with this email exists. Sign in instead.' },
    ...
  };
}
```

This converts the signup form into a yes/no oracle for "is this email
registered?", and there is no rate limit *per email* (`RATE_LIMITS.SIGNUP`
is per-IP only at 5/hour, generous enough to enumerate a curated list
slowly across a small IP rotation). The login + forgot-password +
resend-verification surfaces are correctly anti-enumerated; signup is
the lone hole.

## Evidence

`apps/transcribe-md/src/actions/auth.ts:319-340`:
```ts
const emailLower = parsed.data.email.trim().toLowerCase();

const existing = await prisma.user.findUnique({
  where: { email: emailLower },
  select: { id: true },
});
if (existing) {
  return {
    ok: false,
    errors: {
      email: 'An account with this email exists. Sign in instead.',
    },
    values: { email: emailLower, name: parsed.data.name },
  };
}
```

Compare with the explicitly anti-enumeration shape on the login path
(`auth.ts:131-176`), which runs a dummy bcrypt to equalize timing
between "email exists + unverified" and "email does not exist". And
on `/api/auth/forgot-password/route.ts:71-130`, where every code path
returns the same 200 JSON regardless of account existence. The
signup divergence breaks the platform-wide invariant.

The comment at `auth.ts:321-324` claims the race between the probe
and the create-transaction is "harmless" because the unique index
catches it — that's fine for *integrity* but the early-probe is
exactly what creates the *enumeration* leak.

## Risk

A targeted attacker with a doctor-email list (from a state medical
board CSV, LinkedIn scrape, etc.) can confirm which doctors hold
QuillMD accounts before pilot-launch — a useful primer for
spear-phishing the verified subset with "your QuillMD account needs
attention" emails that pass the recipient's "is this address
registered there?" sanity check.

In a HIPAA-aware product, knowing that a given clinician's email is
on a medical-scribe SaaS roster is reputational/identifying
information; treating it as enumerable weakens the privacy posture
the marketing site advertises.

## Recommended fix

Two acceptable approaches:

1. **Always-200 signup** like forgot-password: silently send a
   "someone tried to sign up with your email — if it was you, sign
   in here" email to the existing account, return the same UI
   "check your email" state to the form regardless of whether a new
   row was created. Mirrors the established anti-enumeration pattern
   in this codebase and matches the change-email handling at
   `apps/transcribe-md/src/app/api/settings/change-email/route.ts:102-126`.

2. **Generic error** that doesn't distinguish "email taken" from
   "weak password" or "policy violation". Less user-friendly but a
   one-line fix: change the error key from `email` to `_form` and
   the copy to "We couldn't create that account. If you already
   have one, sign in instead.". Add a per-email rate-limit at the
   server-action level (in addition to per-IP) so that even the
   "tried to enumerate" probe attempts get capped.
