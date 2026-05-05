---
id: A02-P1-003
severity: P1
title: Auth rate-limit Map is in-memory per replica — container restart, deploy, or healthcheck recreate clears every bucket
domain: Auth & session security
files:
  - apps/transcribe-md/src/lib/rate-limit.ts:35
  - apps/transcribe-md/src/lib/rate-limit.ts:101
---

## Issue

The rate-limit primitive that gates login, signup, forgot-password,
resend-verification, reset-password, change-password, change-email,
delete-account, audio-upload, and visit-mutation traffic is a single
JavaScript `Map` held in module-scope memory on the transcribe-md
container:

```ts
const buckets = new Map<string, Bucket>();

export function tryConsume(key, limit, windowMs): RateLimitResult {
  const now = Date.now();
  const existing = buckets.get(key);
  if (!existing || existing.resetAt <= now) {
    buckets.set(key, { count: 1, resetAt: now + windowMs });
    ...
  }
  ...
}
```

Every container restart — for healthcheck recovery, image deploy,
OOM kill, scaling, even `docker compose restart transcribe-md` — wipes
this Map and resets every bucket to empty. An attacker who triggers
or watches for a restart gets to consume a fresh `LOGIN: 10/hour/IP`,
`SIGNUP: 5/hour/IP`, and `AUTH_EMAIL: 5/hour/IP` bucket all over again.

In a pre-pilot env where rolling deploys / hot-fix recreates are
common, the effective rate limit is closer to "10/hour/IP between
restarts", and any deploy is a free reset for whatever brute-force
attempt was previously stalled.

The same module's own header acknowledges this (lines 21-25) and
labels it KI-4 in `docs/KNOWN_ISSUES.md`:
```
//   1. In-memory state resets on worker restart.
//   2. Buckets don't cross containers (single transcribe-md replica
//      today — revisit when we horizontally scale).
// See `docs/KNOWN_ISSUES.md` KI-4 for the trigger-to-revisit list
// and the Redis-backed fix path.
```
KI-4's "trigger to revisit" was framed around horizontal scale, but
the more immediate trigger is *production load with restart-triggered
attack windows*, which doesn't require a second replica.

## Evidence

`apps/transcribe-md/src/lib/rate-limit.ts:30-46`:
```ts
interface Bucket {
  count: number;
  resetAt: number;
}

const buckets = new Map<string, Bucket>();
```

The `__resetForTests` export at line 132 is a smoke gun for
"this is a single-process Map". Every consumer call site reads /
writes this Map directly via `tryConsume` — there is no
serialization, no fan-out to Redis, no cross-process synchronization.

The infrastructure already has `redis:6379` in compose
(`docker-compose.yml`) and BullMQ jobs persist across restarts via
that Redis. Wiring the rate-limit through Redis (e.g.,
`@upstash/ratelimit` or a hand-rolled `INCR + EXPIRE`) is a known
pattern; the only reason it hasn't shipped is that KI-4 was
deferred to "later".

## Risk

A patient deploy cadence + an attacker watching `/api/health` for
status flips lets an attacker turn each rolling restart into a
brute-force-quota refill. Combined with the lockout-DoS finding
(A02-P1-002), this also means an attacker who notices a deploy
window can re-fire 5 lockout-trip attempts immediately, keeping a
target account locked across the deploy boundary.

## Recommended fix

Move `tryConsume` to Redis-backed atomic increment with TTL. A
minimal sketch:

```ts
async function tryConsume(key, limit, windowMs) {
  const now = Date.now();
  const slot = Math.floor(now / windowMs);
  const redisKey = `rl:${key}:${slot}`;
  const count = await redis.incr(redisKey);
  if (count === 1) await redis.pexpire(redisKey, windowMs);
  if (count > limit) {
    const ttl = await redis.pttl(redisKey);
    return { allowed: false, retryAfterSec: Math.ceil(ttl / 1000) };
  }
  return { allowed: true, retryAfterSec: 0 };
}
```

Notes:

- The Redis client is already imported in `apps/transcribe-md/src/lib/redis.ts`.
- A wrapper ensuring graceful degradation on Redis-down (fail open
  but log loudly, with a Sentry alert) keeps the worst case
  identical to today's "in-memory" semantics.
- Migrate the `RATE_LIMITS` constant table verbatim — the public
  surface (`checkRateLimit`, `rateLimitOr429`, `clientIpFromHeaders`)
  doesn't change, so the call-sites stay untouched.
