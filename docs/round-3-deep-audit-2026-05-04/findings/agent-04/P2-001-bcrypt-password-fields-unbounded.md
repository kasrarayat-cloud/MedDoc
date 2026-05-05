---
id: A04-P2-001
title: Password Zod fields lack `.max()` — bcrypt CPU-DoS surface
severity: P2
domain: Input validation / DoS
status: open
---

## Summary

Several authentication/account flows accept a password from the request body via Zod `.string().min(N)` with NO upper bound:

- `apps/transcribe-md/src/actions/auth-schemas.ts:18-30` — `SignupSchema.password`: `.min(10)` + 3 character-class regexes, no `.max()`.
- `apps/transcribe-md/src/app/api/auth/reset-password/route.ts:35-40` — `PasswordSchema`: same shape, no `.max()`.
- `apps/transcribe-md/src/app/api/settings/change-password/route.ts:27-32` — `PasswordSchema`: same.
- `apps/transcribe-md/src/app/api/settings/change-email/route.ts:45-48` — `BodySchema.password: z.string().min(1)` (used for proof-of-ownership before sending the change-email confirmation; the password is bcrypt-compared against the stored hash).
- `apps/transcribe-md/src/app/api/settings/delete-account/route.ts:50-55` — `BodySchema.password: z.string().min(1)` (same — compared via bcrypt).
- `apps/transcribe-md/src/actions/auth.ts:13-16` (`LoginSchema`) — `password: z.string().min(1, ...)`, no `.max()`. Compared via bcrypt for both the verification pre-check (line 148) and the dummy-hash timing equalizer (line 173, 248).

Every one of these eventually calls `bcrypt.compare(plaintext, hash)` from the `bcryptjs` package. bcryptjs is a pure-JS bcrypt implementation — it walks the input bytes computing the schedule, and although the algorithm internally caps at 72 bytes, the JS layer still receives, copies, and processes the full plaintext before passing to the native loop. A 50 MB password POSTed to `/login` is a directly weaponizable CPU-DoS — Next.js's body parser will accept the JSON (no per-route body cap on these routes; only the audio routes hard-cap), and bcryptjs will burn the event loop processing it.

Next.js 16 default body limit for App Router route handlers is 1 MB if `bodyParser.sizeLimit` is not overridden. None of these routes override it, so the practical ceiling for one request is ~1 MB. But the dummy-hash branch in login (`actions/auth.ts:173, 248`) runs bcrypt.compare on the user-supplied password against a pre-computed hash on every login — an unauthenticated POST. At 1 MB plaintext per request and the 12-round bcrypt cost factor, an attacker can pin a Node worker for hundreds of ms per request. Combined with the bot-grade rate limit on `/login` this is a slow-but-real CPU exhaustion vector.

## Evidence

`apps/transcribe-md/src/actions/auth.ts:113`:
```ts
const blocked = await actionRateLimitOrError(RATE_LIMITS.LOGIN, { email });
if (blocked) return blocked;
const parsed = LoginSchema.safeParse(raw);
```

`LoginSchema` (`auth-schemas.ts:13-16`):
```ts
export const LoginSchema = z.object({
  email: z.string().email().max(254),
  password: z.string().min(1, 'Password is required'),     // <-- no .max()
});
```

Then line 173 (always-runs branch on login when the user is verified or absent):
```ts
await bcrypt.compare(parsed.data.password, DUMMY_PASSWORD_HASH).catch(() => false);
```

bcryptjs receives the full 1 MB plaintext (Next body limit) and processes it.

`SignupSchema.password` is even more permissive — schema only checks lower/upper/digit, no upper length bound. A 1 MB password would be hashed via `bcrypt.hash(..., 12)` (line 342 of `actions/auth.ts`). One signup POST equals one ~12-round bcrypt hash on a megabyte of plaintext.

## Why P2 not P1

- Next.js body parser caps requests at ~1 MB by default for these routes.
- Per-IP rate limits exist on `/login` (`RATE_LIMITS.LOGIN`), `/signup` (`RATE_LIMITS.SIGNUP`), `/forgot-password` and `/reset-password` (`RATE_LIMITS.AUTH_EMAIL`), `/settings/*` (`RATE_LIMITS.SETTINGS`).
- The realistic harm is "burn CPU more than necessary while behind the rate limit", not "tip over production".

But: all of these are pre-pilot, the limits are coarse, and a megabyte of plaintext will be hashed even on the verified-user path's pre-check. Worth a `.max(256)` everywhere.

## Recommended fix

Tag every password field with `.max(256)` (or 128 — RFC 5321 only restricts e-mail-local-part, not passwords; pick a value > the longest plausible passphrase but small enough to be rejected before bcrypt sees it):

```ts
password: z.string().min(10).max(256)
  .regex(/[a-z]/, ...).regex(/[A-Z]/, ...).regex(/\d/, ...),
```

Apply to: SignupSchema, LoginSchema, the three PasswordSchema declarations in auth/reset-password and settings/change-password, plus the `password: z.string().min(1)` cases in change-email and delete-account.

## Cross-domain hooks

- Agent 09 (DoS / rate-limit): the rate-limit buckets on these endpoints determine how exploitable this is in aggregate.
- Agent 02 (auth): the timing-equalizer dummy-hash compare is what makes this exploitable on the unauthenticated login path; if that's removed for a different reason, the surface shrinks.

## Files

- `/opt/meddoc-pro/apps/transcribe-md/src/actions/auth-schemas.ts`
- `/opt/meddoc-pro/apps/transcribe-md/src/actions/auth.ts`
- `/opt/meddoc-pro/apps/transcribe-md/src/app/api/auth/reset-password/route.ts`
- `/opt/meddoc-pro/apps/transcribe-md/src/app/api/settings/change-password/route.ts`
- `/opt/meddoc-pro/apps/transcribe-md/src/app/api/settings/change-email/route.ts`
- `/opt/meddoc-pro/apps/transcribe-md/src/app/api/settings/delete-account/route.ts`
