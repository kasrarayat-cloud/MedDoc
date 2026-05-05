---
id: A11-P2-004
severity: P2
domain: error-handling-observability
title: Sentry never calls setUser/withScope/setTag in app code — events lack user/practice correlation
---

# A11-P2-004 — Sentry events have no user/practice correlation; cross-event filtering impossible

## Issue

`@sentry/nextjs` and `@sentry/node` both expose `Sentry.setUser({id})`,
`Sentry.setTag('practiceId', ...)`, `Sentry.withScope(scope => …)` for
attaching context to captured events. The TranscribeMD app never calls
any of these. The only places Sentry is referenced in source are:

- `apps/transcribe-md/src/worker-sentry.ts` — `Sentry.init(...)` and
  `Sentry.captureException(err, { tags: { visitId, layer } })` (good!
  worker-side has tagging)
- `apps/transcribe-md/src/lib/log.ts` — only a comment about Sentry
- `apps/transcribe-md/src/worker.ts` — only comments

```
$ grep -rn "Sentry\.setUser\|Sentry\.setTag\|Sentry\.withScope\|Sentry\.setContext" \
    /opt/meddoc-pro/apps /opt/meddoc-pro/packages \
    --include="*.ts" --include="*.tsx"
# (zero matches in source)
```

Result: a Sentry event from the WEB tier carries no `user.id`, no
`practiceId` tag — so when an issue fires for `apps/transcribe-md`, the
on-call engineer sees the stack trace but can't filter "show me all the
errors this practice has hit in the last 24 h" or "is this affecting
ALL doctors or just one?".

Worker-side has visitId+layer tags, which is good — but no userId or
practiceId, so a flaky-API-key scenario specific to one practice's
custom Anthropic key (if that ever ships) would be invisible.

## Evidence

`apps/transcribe-md/src/worker-sentry.ts:51-61` — has tags, no setUser:
```ts
export function captureWorkerException(
  err: unknown,
  ctx: { visitId: string; layer: string }
): void {
  Sentry.captureException(err, {
    tags: { visitId: ctx.visitId, layer: ctx.layer },
  });
}
```

`apps/transcribe-md/sentry.client.config.ts:21` — `sendDefaultPii: false`
(correct posture, but no compensating `setUser({ id: userId })` call
elsewhere — so identification is just zero, not "id-only").

The Next middleware
(`apps/transcribe-md/src/lib/auth.ts` / `lib/nextauth.ts`) is the natural
place to populate Sentry user context once a session is resolved, but no
such call exists.

## Risk

When a real incident hits and Sentry shows 5 distinct issues across the
last hour, ops cannot answer:
- Are these one user (their network is bad) or many?
- Are they all in one practice (a tenant-specific config bug)?
- Is one user disproportionately affected (their browser is in a
  pathological state)?

These are first-questions during triage. Without `user.id` (NOT email/name
— the runbook explicitly says id only) and `practiceId` tag, every Sentry
issue requires a manual database lookup to correlate.

## Recommended fix

1. In `apps/transcribe-md/src/lib/nextauth.ts` (or a new server-side
   middleware), once a session is resolved, call:
   ```ts
   Sentry.setUser({ id: session.user.id });
   Sentry.setTag('practiceId', session.user.practiceId);
   ```
   Note: setUser is per-execution-context. In Next, this lives in a
   `withSentry` server-action wrapper or in the API-route handler before
   any `await`s.

2. In API routes, wrap the `withApiHandler()` helper in `apps/transcribe-md/
   src/lib/api-error.ts:80-107` so it pulls the session and `Sentry.setUser`
   *before* invoking the handler. One change → coverage everywhere.

3. In the worker, extend `captureWorkerException` to take `userId`+
   `practiceId`:
   ```ts
   Sentry.captureException(err, {
     tags: { visitId, layer, practiceId },
     user: userId ? { id: userId } : undefined,
   });
   ```
   The worker already knows both — `worker.ts:236-249` already SELECTs
   `userId` and `user.practiceId`.

4. Add `release` and `environment` (already wired) to verify they
   actually populate when source maps land — see A11-P1-001.
