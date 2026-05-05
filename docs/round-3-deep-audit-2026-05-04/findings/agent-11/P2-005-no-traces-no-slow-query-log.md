---
id: A11-P2-005
severity: P2
domain: error-handling-observability
title: Sentry tracesSampleRate=0 across all configs + no Prisma slow-query log = zero performance visibility
---

# A11-P2-005 — No performance tracing, no slow-query logging — performance regressions invisible

## Issue

All four Sentry inits set `tracesSampleRate: 0` and `profilesSampleRate: 0`
(or `replaysSessionSampleRate: 0` for client). The justification in the
config comment is "Errors only — performance sampling stays off until we
decide on a budget." That's a reasonable cost stance, but combined with
the Prisma config it means there is **no** way to observe a slow query,
slow API route, or N+1 in production:

`packages/db/src/index.ts:57`:
```ts
log: process.env.NODE_ENV === 'development' ? ['warn', 'error'] : ['error'],
```

In production, Prisma logs only errors — no `'query'` (which prints query +
duration), no `'info'` (which surfaces connection-pool warnings). The
`statement_timeout=30000ms` ceiling at the Postgres level (line 40) is the
only safety net — a 25-second query will succeed silently with zero log
output, and on-call has no signal that it ran slow.

Next.js side has nothing analogous either — no slow-route logger, no
request-log middleware that tags routes >2s.

## Evidence

```
$ grep -rn "tracesSampleRate\|profilesSampleRate\|replaysSessionSampleRate" \
    /opt/meddoc-pro/apps /opt/meddoc-pro/packages \
    --include="*.ts" | grep -v node_modules | grep -v ".next"
apps/transcribe-md/sentry.server.config.ts:29:  tracesSampleRate: 0,
apps/transcribe-md/sentry.server.config.ts:30:  profilesSampleRate: 0,
apps/transcribe-md/sentry.client.config.ts:18:  tracesSampleRate: 0,
apps/transcribe-md/sentry.client.config.ts:19:  replaysSessionSampleRate: 0,
apps/transcribe-md/sentry.client.config.ts:20:  replaysOnErrorSampleRate: 0,
apps/transcribe-md/sentry.edge.config.ts:39:  tracesSampleRate: 0,
apps/transcribe-md/src/worker-sentry.ts:22:  tracesSampleRate: 0,
apps/transcribe-md/src/worker-sentry.ts:23:  profilesSampleRate: 0,
```
All zero.

`packages/db/src/index.ts:57` — production log is errors-only.

## Risk

Pre-pilot impact: a single doctor with a quirky usage pattern can degrade
DB performance for everyone (e.g. a `findMany` with no `take:` over a
fast-growing table) and on-call has no signal until a doctor complains
about a stuck spinner or a query times out. The first observable signal
is `statement_timeout=30000` killing the query — which is logged via
the `error` Prisma log level — but that's *after* 30 seconds of pool
contention.

The cost shield (`UPLOAD: { limit: 20 }` per hour per user) means the
total request volume is small; sampling traces at 5–10% is genuinely
free at this scale. Skipping tracing entirely is leaving an obvious
free observability win on the table.

`replaysOnErrorSampleRate: 0` is also notable — Sentry's session replay
is the most useful debugging affordance for "why did this clinician's
form submit fail" *and* it's safe under the existing `redactPhi`
guarantees (Sentry replay supports text masking; transcribe-md's
forms are mostly clinical content which would be masked).

## Recommended fix

1. **Sentry tracesSampleRate**: bump to `0.05` (5 %) on server + edge
   configs. At ~20 visits/doctor/hour and ~10 doctors in pilot,
   that's <1 trace/min — trivial cost, full visibility on the
   slow-route distribution.

2. **Sentry replaysOnErrorSampleRate**: set to `1.0` (only when an
   error actually fires — sessions without errors are not recorded).
   Configure `Replay.maskAllText: true` to comply with PHI posture
   (default is true but make it explicit).

3. **Prisma log**: add `['error', 'warn']` in production AND wire a
   slow-query event listener:
   ```ts
   const prisma = new PrismaClient({
     log: [{ emit: 'event', level: 'query' }, 'error', 'warn'],
   });
   prisma.$on('query', e => {
     if (e.duration > 1000) {
       log.warn('prisma:slow-query', `${e.duration}ms`, {
         query: e.query.slice(0, 200),
         params: '[redacted]',
       });
     }
   });
   ```
   Threshold of 1000 ms is generous; tune down once we have a baseline.

4. **Next route slow-log**: add a tiny middleware (or extend
   `withApiHandler`) to log routes that took >2 s with route+userId. One
   line in the success path. Cheap; useful.

This is P2 because the existing error path is functional and these are
preventive observability improvements; they're cheap to land and unblock
useful dashboards before pilot expansion.
