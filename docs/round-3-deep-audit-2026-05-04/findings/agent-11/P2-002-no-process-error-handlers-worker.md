---
id: A11-P2-002
severity: P2
domain: error-handling-observability
title: Worker has no `process.on('unhandledRejection')` / `uncaughtException` handlers
---

# A11-P2-002 — Worker process resilience: no top-level unhandled-rejection / uncaughtException handlers

## Issue

`apps/transcribe-md/src/worker.ts` is the entry point for the BullMQ
worker container. It boots Sentry via the side-effect import of
`./worker-sentry`, then `await main()` and exits non-zero on a rejection
from `main()`:

```ts
main().catch((err) => {
  console.error(
    '[transcribe-md-worker] fatal:',
    redactPhi(err instanceof Error ? err.message : err)
  );
  process.exit(1);
});
```

But there are no global error handlers:

```
$ grep -rn "uncaughtException\|unhandledRejection" \
    /opt/meddoc-pro/apps/transcribe-md /opt/meddoc-pro/packages
# (no matches outside node_modules)
```

This means a Promise rejection that escapes BullMQ's per-job try/catch
(e.g. inside one of the `void prisma.user.findUnique(...)` fire-and-forget
chains in `worker.ts:808-832`, or inside the BullMQ `worker.on('failed', …)`
listener) becomes a Node "warning" in v22 (no longer a hard exit by
default), and `restart: unless-stopped` does NOT trigger because the process
is still alive.

The web container is in better shape because Next 16 / @sentry/nextjs
auto-installs the global handlers — but the worker's @sentry/node init does
NOT enable global capture by default (you have to opt-in via the
`onUnhandledRejection` integration, which the config doesn't add).

## Evidence

`apps/transcribe-md/src/worker.ts:1080-1086` — the only top-level catch:
```ts
main().catch((err) => {
  console.error(...);
  process.exit(1);
});
```

`apps/transcribe-md/src/worker-sentry.ts:17-46` — Sentry init has no
`integrations: [onUnhandledRejection({ mode: 'strict' })]` and no
`onFatalError` hook.

The worker has fire-and-forget chains that could swallow exceptions:
- `worker.ts:808-832` — `void prisma.user.findUnique(...).then(...).catch(notifyErr)` — if a Promise inside this chain rejects synchronously and the `.catch` is gone, that's an unhandled rejection.
- `worker.ts:702` — `await clearAutomationColumn(...).catch(() => {})` — silent swallow.

## Risk

The "wedged worker" failure mode in A11-P1-003 requires either a deadlocked
fetch or an unhandled rejection that doesn't crash the process. With Node 22's
default `--unhandled-rejections=warn`, a Promise rejection in a non-awaited
context ONLY logs a warning. The worker keeps "running" but its job loop
is in an inconsistent state (e.g. an open Prisma transaction that was never
committed — Postgres holds the lock until the connection is closed by pool
recycle or container restart).

Adding the global handler converts this silent state-corruption mode into
a clean crash + restart, which combined with the BullMQ `attempts:3`
re-pickup means jobs are unaffected.

## Recommended fix

Add to the top of `worker.ts` (after Sentry init):

```ts
process.on('unhandledRejection', (reason) => {
  captureWorkerException(reason, { visitId: 'unknown', layer: 'process' });
  console.error(
    '[transcribe-md-worker] UNHANDLED REJECTION:',
    redactPhi(reason instanceof Error ? reason.message : reason)
  );
  // Crash hard — restart: unless-stopped picks us back up in <5s.
  process.exit(1);
});

process.on('uncaughtException', (err) => {
  captureWorkerException(err, { visitId: 'unknown', layer: 'process' });
  console.error(
    '[transcribe-md-worker] UNCAUGHT EXCEPTION:',
    redactPhi(err.message)
  );
  process.exit(1);
});
```

Alternatively (Node-native): start node with
`--unhandled-rejections=strict` in the Dockerfile.worker CMD —
forces v22 to crash on any unhandled rejection without code changes.

Same treatment applies to the Next app's runtime — but Next/Sentry handles
this in its bootstrap. Verify by adding a `throw new Error('test')` inside
a `setTimeout(() => …, 0)` and confirming Sentry sees it.

For the cleanup-worker boot path (lines 895-960), add a
`cleanupWorker.on('error', err => captureWorkerException(...))` listener —
BullMQ emits `error` for connection-loss events and the listener is
currently absent.
