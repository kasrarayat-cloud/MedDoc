# Domain J — Error States

**Run:** 2026-05-03 20:59 UTC

## Summary

| # | Test | Status | Finding |
|---|---|---|---|
| J1 | 404 page (app + marketing) | ✓ | both render branded 404; HTTP 404 status |
| J2 | Malformed JSON to API | ✓ | `400 {"error":"invalid destinations payload"}` |
| J3 | Pipeline upstream simulation (Deepgram/Anthropic/OpenAI down) | DEFERRED | requires Playwright route blocking + a fresh upload |
| J4 | Database connection lost | NOT TESTED | would require killing postgres mid-request — out of scope |
| J5 | File upload too large (>500MB) | partial — got 409 first | server returned `409 {"error":"visit is already processing or finalized"}` because we used a READY visit. The 500MB cap rejection (early Content-Length check) wasn't triggered for this reason; need a fresh QUEUED visit to test. |
| J6 | API rate-limit hit | covered in Domain A4 (rapid clicks → 429) | confirmed |
| J7 | Empty states | ✓ | dashboard shows "No patients yet" with CTA — verified Round 1 |
| J8 | Loading states | DEFERRED | needs slow-network simulation + screenshot per state |

## Findings

### J-001 — Error responses are JSON-shaped (POSITIVE)

Both the 400 (malformed JSON) and 409 (visit state) responses
return JSON bodies with an `error` field rather than the default
Next.js HTML error page or a stack trace. This means:
- Client code can `.then(r => r.json()).catch(showToast)` reliably
- No PHI / stack traces leak in error responses
- Consistent contract for callers

### J-002 — 4xx error messages are user-friendly (POSITIVE)

Examples:
- `"invalid destinations payload"` (J2)
- `"visit is already processing or finalized"` (J5)

These are actionable: the doctor knows what's wrong without needing
to read source code.

## What was NOT covered

- J3 (upstream API failure simulation) — Playwright route blocking
  on `*deepgram*`, `*anthropic*`, etc. would tell us how the worker
  surfaces those failures to the user. Worth doing in a dedicated
  pipeline-resilience audit.
- J4 (DB connection drop) — destructive; out of scope for read-only.
- J5 size cap — needs a fresh QUEUED visit; test rig didn't have one.
- J8 loading-state inventory — tape per-route screenshot loop with
  `--throttle` would catch layout shift / missing skeletons.
