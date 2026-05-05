---
id: A11-P1-001
severity: P1
domain: error-handling-observability
title: Sentry captures errors with un-uploaded source maps — production stack traces unreadable
---

# A11-P1-001 — Sentry source maps never uploaded; prod errors are minified gibberish

## Issue

The `transcribe-md` Next app initialises Sentry (`@sentry/nextjs` v10.49.0) in
three runtimes (browser / node-server / edge) and the worker initialises
`@sentry/node`, but **`next.config.ts` does NOT call `withSentryConfig`** and
the Dockerfiles do NOT invoke `sentry-cli sourcemaps upload`. The Next standalone
build emits `*.js.map` files into `.next/server/chunks/` (verified — 5+ map
files present in the build artifact), but those maps never reach Sentry.

The release / environment fields are also unbound: `SENTRY_RELEASE` is read in
each config but neither Dockerfile passes a `SENTRY_RELEASE`/`SENTRY_AUTH_TOKEN`
build-arg, so Sentry has no release identifier to associate maps with even if
they were uploaded.

## Evidence

`apps/transcribe-md/next.config.ts:1-19` — plain `export default nextConfig`,
no `withSentryConfig(nextConfig, …)` wrapper, no SDK build plugin.

`apps/transcribe-md/sentry.client.config.ts:14-17`:
```
Sentry.init({
  dsn: dsn || undefined,
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT?.trim() || 'production',
  release: process.env.NEXT_PUBLIC_SENTRY_RELEASE?.trim() || undefined,
```

`apps/transcribe-md/Dockerfile:46-63` — no `ARG SENTRY_*`, no
`SENTRY_AUTH_TOKEN`, no `npx @sentry/cli sourcemaps upload` step.

`apps/transcribe-md/Dockerfile.worker` — no Sentry build wiring at all.

```
$ grep -rln "withSentryConfig\|sentry-cli\|sentryWebpack" /opt/meddoc-pro
package-lock.json
```
(Only the lockfile references the plugin — no source code uses it.)

## Risk

When a clinician hits a 5xx at 2 AM, Sentry will receive an exception with
a stack like `at o.<computed> (chunks/567-abc123.js:1:12345)` — completely
unactionable. The runbook promise ("Sentry is the on-call signal") is empty:
ops sees an alert, opens the issue, and finds minified frames they cannot
map back to a source line. Mean-time-to-diagnose for a real incident
goes from minutes to hours, and the value of having Sentry at all is
roughly zero for client-side and SSR errors.

Doctors having to send screenshots of a console error to support is the
current de-facto debugging path — the on-call engineer is then debugging
blind.

## Recommended fix

1. In `apps/transcribe-md/next.config.ts`, wrap export with
   `withSentryConfig(nextConfig, { silent: true, widenClientFileUpload: true,
   hideSourceMaps: true, disableLogger: true, org, project,
   authToken: process.env.SENTRY_AUTH_TOKEN })`.
2. Add `SENTRY_AUTH_TOKEN` (build-time secret) + `SENTRY_RELEASE` (e.g.
   `${GIT_SHA}`) as build-args in `apps/transcribe-md/Dockerfile` and
   `apps/transcribe-md/Dockerfile.worker`. Pass them through in
   `docker-compose.yml` `build.args`.
3. For the worker (plain Node, not Next), add an explicit
   `npx @sentry/cli sourcemaps upload --release=$SENTRY_RELEASE
   /app/apps/transcribe-md/src` step — or compile the worker via tsc to
   `dist/` with `--sourceMap` and upload that tree.
4. Mirror the same wiring in `apps/marketing` once it gets a Sentry DSN
   (see A11-P2-002).
5. Verify post-deploy by triggering a known error and confirming the
   Sentry issue links to a `src/...` line, not a `chunks/...` minified line.
