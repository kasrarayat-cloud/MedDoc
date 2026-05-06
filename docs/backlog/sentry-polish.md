# Sentry polish backlog — captured 2026-05-06 (PR-O closure)

Three items surfaced during PR-O's NAB investigation. None are
BAA-blocking; the Sentry foundation (T-M16.3 + Round 3 PR-H
PR #121) is complete and `docs/runbooks/sentry-setup.md` walks
the operator from DSN-empty no-op state through BAA-signed
activation.

These items polish the verification + safety surface around the
existing foundation. **Not currently prioritized** — captured
here so future-Kasra (or future-Lead via memory recall) doesn't
re-investigate from scratch.

---

## 1. `/api/health/sentry-test` synthetic-error endpoint

**Status:** OPEN — not currently prioritized.

**Why it'd matter.** The current post-activation verification
(`docs/runbooks/sentry-setup.md` §4) hits a real route
(`curl /visits/__sentry-smoke-test__` with a session cookie) to
trigger a 404→catch-all error and confirm the wire works. That's
fine but couples verification to the visit-detail surface. A
dedicated endpoint that returns 500 with a benign error string
(`Error('sentry-test: synthetic error from /api/health/sentry-test')`)
gives the operator a clean, PHI-free verification path that
doesn't depend on the auth / visit / dashboard surfaces. Useful
for BAA reviewers who want to see "an audit trail of synthetic
events" without that audit trail referencing real visit IDs.

**Rough scope.** ~30 LOC. New file
`apps/transcribe-md/src/app/api/health/sentry-test/route.ts`
that:
- gates on a query param `?token=<TEST_HOOK_TOKEN>` so accidental
  hits don't pollute Sentry
- gates on `process.env.NODE_ENV !== 'production'` OR an explicit
  `SENTRY_TEST_ENDPOINT_ENABLED=true` env so it can be turned off
  cleanly post-activation-sweep
- throws once, returns 500 with a stable JSON body for response
  asserting

**Why not in PR-O.** Not foundation-blocking; current verification
flow works.

---

## 2. Dedicated `redactPhi` test suite

**Status:** OPEN — not currently prioritized.

**Why it'd matter.** `redactPhi` (`packages/ai/src/log.ts`) is
the load-bearing PHI defense for Sentry, log lines, and several
worker error paths. Today it's exercised incidentally via
`packages/ai/src/__tests__/temperature-stripping.test.ts` and
through every test that captures errors, but no dedicated test
file pins each scrubbing branch:

- email regex catches normal emails
- email regex catches `+`-suffixed plus-addressing
- SSN regex catches both `123-45-6789` and `123456789`
- SSN regex doesn't false-positive on phone-shaped numbers
- phone regex catches `(415) 555-0142`, `+1 415 555 0142`,
  international, etc.
- 20-word threshold collapses long strings to `[REDACTED:NNNw]`
- short structured log values pass through unchanged
- `null` / `undefined` inputs return safe stringification
- non-string inputs are JSON-stringified before regex

A `packages/ai/src/__tests__/redact-phi.test.ts` file with one
case per branch above (≥10 cases) would harden the safety
guarantee + catch regressions if anyone tunes the regex.

**Rough scope.** ~120 LOC.

**Why not in PR-O.** Quality-bar work, not a foundation gap.
The existing implementation is correct; tests would prevent
future regressions.

---

## 3. Event-level request-field scrubbing

**Status:** OPEN — not currently prioritized.

**Why it'd matter.** `sendDefaultPii: false` (set in every
`Sentry.init`) covers most PII fields by Sentry's default
behavior — IP addresses, full request headers, cookies. But:

- **`event.request.query_string`** can carry visit UUIDs or
  patient IDs (e.g. `?visitId=abc-123-def`). Visit IDs aren't
  PHI per se, but they're a PII-adjacent correlation key — a
  reviewer could argue they shouldn't ship to Sentry.
- **`event.request.headers`** — `sendDefaultPii: false` strips
  the standard PII headers (cookie, authorization, etc.) but
  leaves user-agent + accept-language. A custom header set
  somewhere up the call chain wouldn't be on the strip list.

Adding an explicit `beforeSend` augmentation that:
- replaces `query_string` with `[scrubbed]`
- narrows `request.headers` to an explicit allowlist
  (`['user-agent', 'accept-language']`)
- deletes `request.cookies` outright

…would close the residual leakage paths. Defense-in-depth on
top of `sendDefaultPii: false` and `redactPhi` already in place.

**Rough scope.** ~50 LOC. New helper in
`packages/ai/src/sentry-event-scrub.ts` (next to the existing
`redactPhi`), called from each `beforeSend` hook in addition to
the string-level scrubber.

**Why not in PR-O.** Defense-in-depth, not a foundation gap.
Sentry's `sendDefaultPii: false` plus `redactPhi` covers the
high-leverage cases; this adds belt to the suspenders.

---

## Resolution decision (write here when picked up)

When any of these items ships, replace its **Status** line above
with the merge SHA + tag, and link the closing PR. If a later
investigation determines an item is no longer needed (e.g. the
BAA reviewer doesn't ask about synthetic-error endpoints),
mark it CLOSED-NAB with the rationale.
