---
id: A02-P1-002
severity: P1
title: Per-user 5-attempt account lockout enables targeted DoS — IP rate limit alone does not block lockout fishing
domain: Auth & session security
files:
  - apps/transcribe-md/src/lib/nextauth.ts:138
  - apps/transcribe-md/src/lib/rate-limit.ts:83
---

## Issue

The NextAuth `authorize()` callback locks an account out of every
sign-in attempt for **15 minutes** after **5 failed bcrypt compares**:

```ts
const LOCKOUT_THRESHOLD = 5;
const LOCKOUT_MINUTES = 15;
const nextCount = user.failedLoginCount + 1;
const shouldLock = nextCount >= LOCKOUT_THRESHOLD;
const lockUntil = shouldLock
  ? new Date(Date.now() + LOCKOUT_MINUTES * 60 * 1000)
  : null;
await prisma.user.update({
  where: { id: user.id },
  data: {
    failedLoginCount: { increment: 1 },
    ...(lockUntil ? { lockedUntil: lockUntil } : {}),
  },
});
```

The IP-level rate limit on `loginAction` is `LOGIN: 10/hour/IP`
(`rate-limit.ts:83`). An attacker rotating across, say, 50 IPs (Tor
exit nodes, residential proxies) can submit 250 wrong-password
attempts/hour against any known email — far more than the 5 needed
to lock the legitimate user out. Once locked, the legitimate doctor
sees only "Invalid email or password" (the loginAction does not
surface a `lockedUntil` message) and cannot sign in to their clinical
surface for 15 minutes. The attacker can repeat indefinitely (every
window) at minimal cost.

The lockout itself is good defense-in-depth against credential-stuffing,
but the absence of a per-email/per-account *attempt* cap (separate
from the success cap) means the same mechanism becomes a denial-of-
service primitive against any user whose email is known.

## Evidence

`apps/transcribe-md/src/lib/nextauth.ts:135-172`:
```ts
const valid = await bcrypt.compare(password, user.passwordHash);
if (!valid) {
  const LOCKOUT_THRESHOLD = 5;
  const LOCKOUT_MINUTES = 15;
  const nextCount = user.failedLoginCount + 1;
  const shouldLock = nextCount >= LOCKOUT_THRESHOLD;
  ...
  await prisma.user.update({
    where: { id: user.id },
    data: {
      failedLoginCount: { increment: 1 },
      ...(lockUntil ? { lockedUntil: lockUntil } : {}),
    },
  });
  ...
  return null;
}
```

`apps/transcribe-md/src/lib/rate-limit.ts:83`:
```ts
LOGIN:         { bucket: 'login',         limit: 10, windowMs: HOUR_MS },
```

Note also the rate-limit comment at the top of the file:
```ts
//  1. In-memory state resets on worker restart.
//  2. Buckets don't cross containers (single transcribe-md replica
//     today — revisit when we horizontally scale).
```
The IP cap is per-replica in-memory, so even a single attacker without
rotation gets a free pass after each container restart (rolling
deploys, healthcheck-driven recreates).

## Risk

A motivated attacker — a competitor demoing alternatives, a disgruntled
former employee, anyone with a grudge — can keep the highest-value
admin or pilot-doctor accounts perma-locked through pilot launch by
firing 5 wrong-password attempts/window from a moderate IP pool. The
victim has no in-band recovery: the only paths back in are
`forgot-password` (works because forgot-password doesn't check
`lockedUntil`), waiting 15 min, or contacting support. None are good
during a live patient encounter where the doctor needs to record a
note now.

Login DoS during a live medical workflow is patient-safety adjacent.

## Recommended fix

Layered:

1. **Cap *attempts* per email per window in addition to per-IP.**
   Add a new `LOGIN_PER_EMAIL: { limit: 20, windowMs: HOUR_MS }`
   bucket and consume it in `loginAction` keyed by the lowercase
   email. Distinct from the lockout — this caps *traffic*, not
   *failures*, so it works against rotating IPs.

2. **Exponential lockout backoff instead of binary.** Today's
   binary 15-min lock is easy to weaponize. Schemes like 1 min →
   5 min → 30 min → 24 h (decaying back over a successful login)
   make sustained DoS expensive while staying light on the legit
   "I fat-fingered my password three times" path.

3. **Surface unlock-via-email.** When `lockedUntil` is set, `loginAction`
   could (with timing equalization) offer an "unlock my account"
   affordance that emails a one-time `consumeAuthToken({ purpose:
   ACCOUNT_UNLOCK })`-style link. Lets the victim reach back in
   without waiting 15 min.

4. **Move the rate-limit map to Redis.** The in-process Map at
   `rate-limit.ts:35` doesn't survive container restarts and
   doesn't cross replicas — a known limitation flagged in
   `docs/KNOWN_ISSUES.md` KI-4. Pre-pilot is the right time to
   fix it; the Redis container is already running and used by the
   BullMQ worker.
