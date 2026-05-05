---
id: A11-P3-001
severity: P3
domain: error-handling-observability
title: 429 rate-limit response body lacks ETA — only Retry-After header
---

# A11-P3-001 — 429 body says "Try again later" with no human-readable wait time

## Issue

`apps/transcribe-md/src/lib/rate-limit.ts:160-175` — when a request hits
its bucket limit, the response is:

```ts
return NextResponse.json(
  { error: 'Too many requests. Try again later.' },
  {
    status: 429,
    headers: { 'Retry-After': String(rl.retryAfterSec) },
  }
);
```

The `Retry-After` header is correct (great — RFC 9110 compliant). But the
JSON body just says "Try again later." with no numeric ETA, and the
existing client code that displays the error to the doctor (`toast.error(
err.message)` in `voice-dictator.tsx:146`, `text-composer.tsx:76`, etc.)
generally renders the JSON `error` field directly — so the doctor sees
"Too many requests. Try again later." with no idea how long.

Worse: the client doesn't read the `Retry-After` header at all, so even
the data we DO send is unused.

## Evidence

`apps/transcribe-md/src/lib/rate-limit.ts:160-175` (quoted above).

`apps/transcribe-md/src/components/voice-dictator.tsx:146`:
```ts
console.error('[voice-dictator] upload failed:', err);
toast.error(err.message ?? 'Upload failed');
```
No special-casing for 429, no Retry-After read.

`apps/transcribe-md/src/components/text-composer.tsx:76` similar.

`apps/transcribe-md/src/components/command-palette.tsx:67` similar.

## Risk

Polish — but the rate limiter is the only thing standing between the
product and a runaway $$$ bill from Anthropic+Deepgram, and the doctor
hitting the limit (e.g. `UPLOAD: 20/hour` after a short burst of test
visits during onboarding) gets a bland message that doesn't help them
plan their next move. They retry in 30 seconds, get 429 again, retry,
get 429 again, and eventually give up or contact support. Support has
to explain "you're rate-limited, wait an hour" — embarrassing.

## Recommended fix

Two-line change in `rate-limit.ts`:
```ts
return NextResponse.json(
  {
    error: `Too many requests. Try again in ${humanizeSeconds(rl.retryAfterSec)}.`,
    code: 'RATE_LIMITED',
    retryAfterSec: rl.retryAfterSec,
  },
  { status: 429, headers: { 'Retry-After': String(rl.retryAfterSec) } }
);
```
Where `humanizeSeconds(35) = '35 seconds'`, `humanizeSeconds(2700) =
'45 minutes'`. Simple helper, no external dep.

Client-side, update the toast/error display (one place: extend the
existing fetch wrapper or `withApiHandler` client equivalent) to
prefer the `retryAfterSec` field if present and display "Try again in 45
minutes" instead of just "Try again later".

Also consider: the AUTH_EMAIL bucket is 5 requests/hour — on password
reset, a doctor could plausibly hit this if a typo + retry cycle takes
6 attempts. The error body should say "5 password resets per hour" so
the user understands; today it says only "Too many requests." For
HIPAA-adjacent surfaces, opaque rate limits read as "the system is
broken" rather than "you've hit the per-account safety limit."

P3 because it's UX polish and the limit values themselves are sensible.
