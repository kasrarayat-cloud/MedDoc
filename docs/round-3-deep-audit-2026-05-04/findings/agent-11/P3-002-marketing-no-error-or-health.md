---
id: A11-P3-002
severity: P3
domain: error-handling-observability
title: Marketing site has no error.tsx, no /api/health — homepage healthcheck couples render and liveness
---

# A11-P3-002 — Marketing app missing `error.tsx`, missing `/api/health`, healthcheck downloads home page

## Issue

(See A11-P1-005 for the Sentry-side gap; this is the smaller-scope cousin
focused on healthcheck quality + boundary coverage.)

`apps/marketing/src/app/` has only:
- `layout.tsx`
- `page.tsx`
- `not-found.tsx`
- `globals.css`, `landing.css`, `icon.svg`

Missing:
- `error.tsx` (Next App Router boundary for unhandled render errors)
- `global-error.tsx` (catches errors in the root layout)
- `api/health/route.ts`

The Docker healthcheck at `docker-compose.yml:288` is:
```
test: ["CMD", "wget", "-qO-", "--spider", "http://127.0.0.1:3010/"]
```
which downloads the entire static landing page (~hundreds of KB of HTML
+ inlined CSS + framer-motion bundle hash references) every 30 seconds.
That conflates "render works" with "process alive" and is wasteful at
~80 hits/hour per healthcheck cycle.

## Evidence

```
$ ls /opt/meddoc-pro/apps/marketing/src/app/
globals.css  icon.svg  landing.css  layout.tsx  not-found.tsx  page.tsx

$ find /opt/meddoc-pro/apps/marketing/src -name "route.ts"
# (zero matches)

$ grep -n "healthcheck:" -A 4 /opt/meddoc-pro/docker-compose.yml | head -30
... 
healthcheck:
  test: ["CMD", "wget", "-qO-", "--spider", "http://127.0.0.1:3010/"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 30s
```

## Risk

Three small but real concerns:

1. A render-time error in a marketing page (e.g. broken `<Image>` src
   that throws at hydrate time on an iOS browser) shows the default Next
   error overlay in dev and a blank page in production. With no
   `error.tsx`, the recovery UX is "user reloads and sees the same
   blank page". With no Sentry (A11-P1-005), nobody knows.

2. The healthcheck downloading the whole homepage means a slow Caddy
   tick can OOM the small marketing container under odd circumstances
   (extremely unlikely at 256 MB mem_limit, but the cost to fix is
   trivial).

3. Healthcheck-as-render is a stale-staleness signal: if `/` is cached
   for 60 s (Next ISR) the healthcheck doesn't actually exercise the
   running process — it might be served from the in-process cache
   while a fresh request would hit a broken codepath. A dedicated
   `/api/health` confirms the request handler is responding.

## Recommended fix

1. Add `apps/marketing/src/app/api/health/route.ts`:
   ```ts
   import { NextResponse } from 'next/server';
   export const runtime = 'nodejs';
   export const dynamic = 'force-dynamic';
   const startedAt = Date.now();
   export function GET() {
     return NextResponse.json(
       { status: 'healthy', uptime_seconds: Math.floor((Date.now()-startedAt)/1000) },
       { headers: { 'Cache-Control': 'no-store' } }
     );
   }
   ```
   Update compose healthcheck to point at `/api/health`.

2. Add `apps/marketing/src/app/error.tsx` and `global-error.tsx`. Even a
   minimal `<h1>Something went wrong</h1><Link href="/">Back home</Link>`
   is better than a blank page.

3. Once Sentry is wired (A11-P1-005), have `error.tsx` capture via
   `Sentry.captureException(error)` so silent marketing-page errors
   become visible.

P3 because marketing is unauth, no PHI, and the impact of not having
these is "uglier failure UX for cold prospects" — small in the broader
list. Land alongside A11-P1-005 in one marketing-app uplift PR.
