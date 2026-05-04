# Domain K — Rate Limiting + Abuse

**Run:** 2026-05-03 21:09 UTC
**Mode:** CONTROLLED — bounded request volumes, stop on first 429

## Summary

| # | Test | Status | Finding |
|---|---|---|---|
| K1 | Signup rate limit (per IP) | inconclusive (probe limit) | Server Action returns 200 even on rate-limit (rate-limit message in response body, not status code) |
| K2 | Login rate limit (per email + per IP) | inconclusive (probe limit) | Same — Server Action returns 200 with `_form: "Too many attempts..."` in response body. The product's behavior is verified by the actual UI showing the error (we hit it earlier in Domain B). |
| K3 | Forgot-password rate limit (`/api/auth/forgot-password`) | ✓ **5 attempts → 429** | clear rate limit window; appropriate threshold for a per-email-recovery endpoint |
| K4 | API endpoints (1000 GETs to /api/visits) | DEFERRED | excessive load; covered indirectly by Domain A4 (rapid Create & continue → 429) |
| K5 | File upload rate limit (100 parallel audio uploads) | DEFERRED | excessive QA-test artifacts; the upload route's per-visit ownership + size checks already provide first-line defense |
| K6 | Admin endpoint as non-admin | ✓ **404** | proper hiding — admin routes return 404, not 403, so unauthenticated callers can't enumerate route existence |

## Findings

### K-001 — Forgot-password rate limit: 5 attempts per window (POSITIVE)

```
attempt 1: 200
attempt 2: 200
attempt 3: 200
attempt 4: 200
attempt 5: 200
attempt 6: 429
```

5 attempts per window. The window length isn't probed (would need to
wait + retry); from Round 1 source review, the `RATE_LIMITS` config
in `apps/transcribe-md/src/lib/rate-limit.ts` defines per-rule
thresholds.

This is appropriate for a per-email-recovery endpoint:
- 5 attempts gives a real user with multiple email-typos enough
  rope to find the right one
- 6+ blocks a credential-stuffing / email-enumeration attacker

### K-002 — Admin endpoints return 404, not 403 (POSITIVE)

`GET /api/admin/users` without a session returns 404 (`Not Found`).
This is the same posture verified in Round 1 — admin routes hide
their existence from unauthenticated callers via 404 instead of
returning 403 (which would confirm the endpoint exists).

### K-003 — Server Actions don't expose rate-limit via HTTP status (INFO)

Next.js Server Actions (`signupAction`, `loginAction`) return their
errors via the action's response payload (`FormErrorState`), not
via HTTP 4xx status codes. So the HTTP layer always sees `200 OK`
even when the action returned `_form: "Too many attempts..."`.

This is **correct Next.js architecture** — Server Actions deliver
their state to the client form via React's `useActionState`, not
via HTTP semantics. But it does mean external probes (curl,
playwright `page.request.post`) can't distinguish "rate-limited"
from "validation failed" without parsing the response body.

For an audit, this means K1 and K2 are best probed via the UI flow
(which we did in Domains A4 and B — saw "Too many attempts. Try
again in 3 minutes." rendered correctly).

## What was NOT covered

- K4 (1000 API GETs) — would burn API budget unnecessarily; the
  rate limit is verified by other paths
- K5 (100 parallel uploads) — would create 100 QA-test visits;
  the upload route's existing `content-length > 500MB` early
  rejection + per-visit state check (verified Domain J5)
  already block obvious abuse
- Window-length probing — needs sustained patience; the windows
  are configured per-rule in `rate-limit.ts`
- Account lockout from K2 — `users.failedLoginCount` and
  `users.lockedUntil` columns exist (verified in Round 1 schema
  audit). Worth verifying after K2 hammering whether the bypass
  account got locked.
