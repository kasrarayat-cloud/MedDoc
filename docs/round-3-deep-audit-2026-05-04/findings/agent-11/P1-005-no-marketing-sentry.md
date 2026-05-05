---
id: A11-P1-005
severity: P1
domain: error-handling-observability
title: Marketing app has no Sentry instrumentation — landing-page errors invisible
---

# A11-P1-005 — apps/marketing has zero error reporting (no Sentry, no client-error sink)

## Issue

`apps/marketing/` is the public landing site at quillmd.com /
www.quillmd.com — the front door of the product. It has:

- No `sentry.client.config.ts` / `sentry.server.config.ts` / `sentry.edge.config.ts`
- No `instrumentation.ts`
- No `@sentry/nextjs` dependency in `package.json`
- No `/api/health` route, no `/api/client-errors` sink
- No structured logger
- No error.tsx (only `not-found.tsx`)

The Docker healthcheck for marketing hits `http://127.0.0.1:3010/` — the
home page itself. So the only signal "marketing is OK" is whether the
home page renders. Any in-page React error that the SSR step survives
will reach a real prospect's browser and silently fail. There is no
console-error reporting, no beacon, no SDK.

## Evidence

```
$ ls /opt/meddoc-pro/apps/marketing/
Dockerfile  eslint.config.mjs  next.config.ts  next-env.d.ts
package.json  postcss.config.mjs  public  src  tsconfig.json
# no sentry.* configs

$ cat /opt/meddoc-pro/apps/marketing/package.json
{
  ...
  "dependencies": {
    "@meddoc/shared": "*",
    "@radix-ui/react-accordion": "^1.2.1",
    "clsx": "^2.1.1",
    "framer-motion": "^11.11.11",
    "lucide-react": "^1.7.0",
    "next": "^16.2.4",
    "react": "19.2.4",
    "react-dom": "19.2.4",
    "tailwind-merge": "^2.5.4"
  },
  ...
}
# no @sentry/nextjs

$ find /opt/meddoc-pro/apps/marketing/src -type f -name "route.ts"
# (no API routes at all)
```

`docker-compose.yml:286-292`:
```yaml
healthcheck:
  test: ["CMD", "wget", "-qO-", "--spider", "http://127.0.0.1:3010/"]
```

## Risk

Three concrete failure modes go undetected:

1. **Pricing typo / dead CTA**: a `<Link href>` regression sends every
   would-be signup to `/dashboard` (404 on marketing). Marketing 404s
   show up nowhere.

2. **Hydration mismatch on iOS Safari** (a common Next 16 / React 19
   class of bug): a fraction of visitors see a broken landing page,
   bounce. No alert.

3. **Phone-home leak**: marketing imports `@meddoc/shared` and Lucide;
   a future refactor accidentally pulls in a Node-only API in a client
   component → 500 on `/`. Caddy 502 → real prospects see Caddy's
   default error page (see A11-P3-002 too). No on-call alert.

Marketing is the highest-traffic surface with the lowest observability —
the inverse of what we want.

## Recommended fix

Three small additions, mirroring the transcribe-md pattern:

1. Add `@sentry/nextjs` to `apps/marketing/package.json`. Create
   `sentry.client.config.ts` (browser) and `sentry.server.config.ts`
   (the Node-side cases that survive SSR). Reuse `redactPhi()` from
   `@meddoc/ai` for `beforeSend` — even though marketing is unauth,
   query-string params can leak email if a prospect bookmarks
   `/?email=foo@bar.com`.

2. Add `apps/marketing/src/app/api/health/route.ts` returning
   `{status:'healthy', uptime}` and switch the compose healthcheck to
   `wget --spider http://127.0.0.1:3010/api/health`. The current
   "GET /" check downloads the entire static landing page on every
   tick — wasteful and conflates render with liveness.

3. Add `apps/marketing/src/app/error.tsx` mirroring transcribe-md's
   `ErrorFallback` component. Even a 1-line stub that POSTs to
   `/api/client-errors` (when added) is better than zero coverage.

If Sentry budget is the blocker, route marketing's DSN to the same
Sentry project as transcribe-md with a `service: marketing` tag.
Adding a project later is trivial.
