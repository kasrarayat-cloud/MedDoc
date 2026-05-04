# P2-001 — Signup email field has no max-length validation

**Severity:** P2 (DB pollution / row-overflow attack surface)
**File:** `apps/transcribe-md/src/actions/auth.ts:64-76` — `SignupSchema`

## What

The signup Zod schema:
```ts
const SignupSchema = z.object({
  email: z.string().email(),  // ← no max length
  password: z.string().min(10).regex(...).regex(...).regex(...),
  name: z.string().min(1).max(120),
  acceptTerms: z.literal('on', ...),
});
```

`z.string().email()` validates email FORMAT (presence of `@`,
domain shape) but does NOT enforce a length cap. RFC 5321 caps
email local-part at 64 chars and total at 254 chars.

Round 2 verified that a 180-char-local-part email was accepted +
auto-confirmed by the QA bypass. DB row was created with the
oversized email intact.

## Why it matters

- DB pollution: an attacker can create thousands of accounts with
  arbitrarily long email addresses to:
  - Inflate `users` table size (10k accounts × 250-byte emails =
    2.5MB just for emails)
  - Break admin UI tables that don't truncate display
  - Confuse downstream tools (Resend, audit logs) that may have
    their own length assumptions
- Combined with `EMAIL_AUTO_CONFIRM_DOMAINS` bypass: any
  `*@quillmd-test.local` long email gets auto-verified, expanding
  the attack surface for QA-test pollution
- `name` field is correctly capped at `max(120)` — only `email` was
  missed

## Reproduction

```ts
const longEmail = 'a'.repeat(180) + '@example.com';
// signupAction({ email: longEmail, password: 'Strong1!Aa', name: 'X', acceptTerms: 'on' })
// → row created in users table with 192-char email
```

Verified live: see `[QA-BYPASS] auto-confirmed email for aaa…aaa-1777839763@quillmd-test.local`
in container log (2026-05-03 20:23 UTC).

## Risk if NOT fixed

- DB-pollution / oversized-row attack
- Inconsistent rendering in admin UI tables that assume
  reasonable email lengths
- Possible 4xx from downstream services (Resend caps `to` at 254
  chars per RFC; sending to a >254-char address would 4xx and
  inflate failed-delivery counts)

## Proposed remediation

```diff
const SignupSchema = z.object({
- email: z.string().email(),
+ email: z.string().email().max(254),  // RFC 5321 total length cap
  password: z.string().min(10)...,
  name: z.string().min(1).max(120),
  acceptTerms: z.literal('on', ...),
});
```

Same caps should be applied to:
- `apps/transcribe-md/src/app/api/settings/change-email/route.ts`
- Any other signup-like flow
- The `LoginSchema` already only validates `email()` without max —
  also worth adding `.max(254)` for symmetry

## Effort

- Code change: 1-line per Zod schema (~3 places)
- Smoke test: ~5 min
- Total: ~10 min

## Risk to fix

VERY LOW — strictly tightens validation; rejects only emails
that exceed RFC 5321. No real user has a 254+ char email.

## Status

Plan-only per audit rules.
