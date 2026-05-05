---
id: A11-P3-003
severity: P3
domain: error-handling-observability
title: No central middleware redacts Authorization / cookies / password fields from log lines
---

# A11-P3-003 — Log redaction is per-call-site `redactPhi`; no header/cookie/password scrubber

## Issue

`packages/ai/src/log.ts:67-90` provides `redactPhi()` — a regex sweep
that masks emails, phones, SSNs, and collapses long free-text. Every
`console.error` site that catches an error calls `redactPhi(err.message)`
manually (e.g. `worker.ts:741`, `api-error.ts:101`, `queue.ts:30`).

What `redactPhi` does NOT cover:

- HTTP `Authorization: Bearer ...` headers if they appear in an error
  message (Anthropic SDK errors sometimes echo the request URL with
  query params — keys aren't in URLs there but a future SDK upgrade
  could change this).
- Cookies or `Set-Cookie` headers if a Prisma error (it shouldn't
  but…) or an SSR rendering error includes them.
- Field names like `password`, `secret`, `token`, `apiKey` — the
  current scrubber doesn't pattern-match `password=foo123` or
  `Bearer sk-abc`.
- The structured `data` blob passed to `log.info(scope, msg, data)` —
  the wrapper does not redact, on the assumption callers pass only
  known-safe fields. That's a code-discipline bet that breaks the
  first time a contributor logs a request body.

There's no logger middleware that mounts a denylist of header/field
names and zaps them automatically.

## Evidence

`apps/transcribe-md/src/lib/log.ts:18-19`:
```ts
// NOTE: beforeSend in Sentry's init already scrubs via redactPhi on
// anything it captures from console output. This wrapper does NOT
// re-redact — callers pass only known-safe fields into `data`. If a
// value might carry PHI, redactPhi it before passing.
```
Explicit "callers must remember" — exactly the kind of discipline that
breaks under a release-pressure deploy.

`packages/ai/src/log.ts:76-90` — `redactPhi` regex set:
```
EMAIL_RE  /\b[\w.+-]+@[\w-]+\.[\w.-]+\b/g
PHONE_RE  /\(?\+?\d[\d \-()]{8,}\d/g
SSN_RE    /\b\d{3}-?\d{2}-?\d{4}\b/g
MAX_WORDS_BEFORE_REDACT = 20
```
No password / token / Bearer / cookie / api_key patterns.

## Risk

Hypothetical but real:

1. A future fetch wrapper logs failed requests including headers (someone
   adds `console.error('[fetch]', err, { headers: req.headers })`). An
   `Authorization: Bearer sk-anthropic-...` lands in stdout, gets shipped
   to whatever log aggregator we eventually use, and now the API key is
   in a log retention you didn't plan for.

2. Worker's `redactPhi(err.message)` doesn't catch a Deepgram error that
   happens to include the API key in its message body (Deepgram's error
   surface doesn't quote keys today, but a future change could).

3. NextAuth session cookies in a server-component error stack — the
   stack trace might include `request.cookies` if the rendering
   exception was thrown inside a header read.

These are low-probability today (the call sites really do follow the
"only safe fields" pattern), but the lack of a central enforcement
layer means risk grows linearly with code surface.

## Recommended fix

Extend the structured logger in `apps/transcribe-md/src/lib/log.ts`
(and create `apps/marketing/src/lib/log.ts` if A11-P1-005 lands) with
a default scrubber that runs on every `data` payload:

```ts
const REDACTED_KEYS = /^(password|passwd|secret|token|api_?key|cookie|authorization|x-csrf|set-cookie)$/i;
const BEARER_RE = /Bearer\s+[A-Za-z0-9._-]+/g;
const APIKEY_RE = /sk-[A-Za-z0-9-_]{16,}/g;

function scrubData(d: unknown): unknown {
  if (!d || typeof d !== 'object') return d;
  if (Array.isArray(d)) return d.map(scrubData);
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(d)) {
    if (REDACTED_KEYS.test(k)) { out[k] = '[REDACTED]'; continue; }
    if (typeof v === 'string') {
      out[k] = v.replace(BEARER_RE, 'Bearer [REDACTED]')
                .replace(APIKEY_RE, 'sk-[REDACTED]');
    } else out[k] = scrubData(v);
  }
  return out;
}
```

Then `emit()` in `lib/log.ts` calls `scrubData(data)` before stringify.
Combined with the existing redactPhi for free-text strings this gives
defense-in-depth: PHI text is collapsed AND structured secrets are
zapped, with no per-call-site discipline required.

Same scrubber should be applied inside `withApiHandler`'s catch (line 91-104)
when stringifying `err` — today it only calls `redactPhi(err.message)`,
which lets `err.cause` or `err.stack` through unscrubbed.

P3 because the current per-site discipline appears to be holding and
no observed leak is in the audit. Worth landing as preventive
hygiene before the codebase grows to a point where the discipline
breaks.
