---
id: A02-P2-001
severity: P2
title: Password policy lacks breach-list (HIBP) integration and length cap; no upper-bound or specials-required gate
domain: Auth & session security
files:
  - apps/transcribe-md/src/actions/auth-schemas.ts:18
  - apps/transcribe-md/src/app/api/auth/reset-password/route.ts:35
  - apps/transcribe-md/src/app/api/settings/change-password/route.ts:27
---

## Issue

The password policy in three call sites (signup, reset, change) is
identically:

```ts
z.string()
  .min(10, 'Password must be at least 10 characters')
  .regex(/[a-z]/, 'Password must contain a lowercase letter')
  .regex(/[A-Z]/, 'Password must contain an uppercase letter')
  .regex(/\d/, 'Password must contain a digit');
```

Reasonable on length + complexity, but absent:

1. **No max length.** `z.string().min(10)` accepts an arbitrarily
   long password. bcrypt truncates inputs to 72 bytes (the algorithm
   limit), so `"A"*72 + <whatever>` collapses to a single hash —
   different long passwords with the same 72-byte prefix become
   *equivalent*, which is non-obvious and breaks the user's mental
   model. A `.max(72)` (or 128) makes the truncation explicit.
2. **No breach-list check.** Passwords like `Password123` (12 chars,
   passes the regex) appear in every credential dump and rolling
   compilation. A k-anonymity HIBP lookup (`api.pwnedpasswords.com/range/{first5}`)
   adds ~50ms and rejects the 600M most-known-breached passwords.
3. **No similarity check against email/name.** A doctor whose name
   is "Anna Smith" picking `Anna1234567` clears the regex but is
   trivially guessable from public profile data.
4. **No specials-required.** Regulated-industry expectations
   (NIST 800-63B, HIPAA's "reasonable safeguards" reading) typically
   ask for *one of* length-or-complexity. The 10-char + mixed-case +
   digit floor is borderline for clinical SaaS; many institutional
   security teams will flag the absence of a special-character
   requirement during procurement review.
5. **No history check.** Reset and change-password flows don't
   prevent reusing the previous hash (only the immediate "new ===
   current" check at `change-password/route.ts:45`), so a user can
   alternate between two passwords every other reset.

## Evidence

`apps/transcribe-md/src/actions/auth-schemas.ts:18-26`:
```ts
export const SignupSchema = z.object({
  email: z.string().email().max(254),
  password: z
    .string()
    .min(10, 'Password must be at least 10 characters')
    .regex(/[a-z]/, 'Password must contain a lowercase letter')
    .regex(/[A-Z]/, 'Password must contain an uppercase letter')
    .regex(/\d/, 'Password must contain a digit'),
  name: z.string().min(1, 'Name is required').max(120),
  ...
});
```

The signup hint copy at `signup-form.tsx:139` reflects the same
policy.

## Risk

A pilot doctor who chooses `Welcome2026!` (12 chars, passes the
regex, in every breach list) is now reusing a password that maps to
their personal-bank login on a system that holds patient PHI. The
credential-stuffing risk is the leading entry-vector for SaaS
breaches in 2024-2026 industry reports.

For a HIPAA-aware product, *not* gating against the public breach
corpus is a question that comes up in every SOC 2 / HITRUST
control-mapping review.

## Recommended fix

Layered:

1. **Add `.max(72)`** to the schema across all three call sites.
   Simplest change, removes the bcrypt-truncation footgun.

2. **Add HIBP k-anonymity check** server-side in the schema-after
   step (Zod `.refine` won't help because it's sync; do it after
   `safeParse`). Cache hits via Redis with 30-day TTL so repeated
   checks of the same prefix don't hammer HIBP. ~50ms p99,
   acceptable on the password-set hot path.

3. **Forbid password ∈ { email, name, "quillmd" }** with a simple
   case-insensitive substring check.

4. **Optional: keep last-3 password hashes** in a `PasswordHistory`
   table and reject the new password if it matches any. Light
   schema add; clinical-SaaS compliance reviewers ask for it.

5. **Bump min length to 12** to align with NIST 800-63B's mid-AAL
   recommendation. Existing accounts are not retroactively forced
   to rotate (ride out their natural reset cadence).
