---
id: A11-P1-003
severity: P1
domain: error-handling-observability
title: transcribe-md-worker has NO Docker healthcheck — silent zombie / livelock undetected
---

# A11-P1-003 — Worker container has no HEALTHCHECK; ops will not see a wedged worker

## Issue

`apps/transcribe-md/Dockerfile.worker` does not declare `HEALTHCHECK`, and the
`transcribe-md-worker` service in `docker-compose.yml` (lines 306-371) has no
`healthcheck:` block either.

The worker is the most failure-prone component in the stack — it talks to
three external providers (Deepgram, Anthropic, MinIO), holds long fetches open
for the duration of a 10-minute Deepgram batch, and runs five parallel
automation layers. Yet a wedged worker (stuck fetch, deadlocked Prisma
connection, infinite loop in JSON.parse on a malformed model response,
ioredis dropped connection that never reconnects, unhandled rejection in a
floating Promise) will:

- Continue to report "running" in `docker ps`
- Continue to satisfy `restart: unless-stopped` (the process is alive, just
  not making progress)
- Show no signal in any health probe — `/api/admin/system/health` only
  reports queue *depth*, not worker liveness (and the worker doesn't
  publish a heartbeat key)

The web app's `/api/health` does NOT probe the worker (see comment at the
top of `apps/transcribe-md/src/app/api/admin/system/health/route.ts:9-17`:
"we don't have docker-socket access… can't check the worker container").
The cleanup-heartbeat (`apps/transcribe-md/src/lib/cleanup-heartbeat.ts`)
only confirms cron sweeps ran, not that the *main* `process_visit`
consumer is alive.

## Evidence

```
$ grep -n "HEALTHCHECK\|healthcheck:" apps/transcribe-md/Dockerfile.worker docker-compose.yml | grep -i worker
docker-compose.yml:306:  transcribe-md-worker:
# (no HEALTHCHECK line below)
```

`apps/transcribe-md/Dockerfile.worker:46-90` — the runner stage ends with
`CMD ["npx", "tsx", "src/worker.ts"]` and no `HEALTHCHECK`.

By contrast `apps/transcribe-md/Dockerfile:107-108` correctly has
`HEALTHCHECK ... wget --spider http://127.0.0.1:3011/api/health`.

`apps/transcribe-md/src/worker.ts:1057-1068` — the worker emits BullMQ event
listeners (`completed`, `failed`) but does NOT write a "I am alive" key to
Redis on a periodic timer.

## Risk

The 2-AM scenario the runbook is supposed to cover:

1. Worker hits an unhandled rejection in the `Promise.allSettled` of the
   automation fan-out. The unhandled rejection terminates the BullMQ
   worker's job loop but the Node process stays up because there are
   still active timers (the cleanup scheduler, the open ioredis
   connection).
2. BullMQ shows zero active jobs but the queue depth keeps climbing.
3. Doctor uploads visit at 23:00 → never processed.
4. On-call engineer wakes up to "doctor reports stuck visits" at 02:00.
5. Engineer checks `docker ps` — `transcribe-md-worker` is `Up 14 hours
   (running)`. Engineer checks `/api/admin/system/health` — postgres OK,
   redis OK, MinIO OK, queue depth 17. Engineer sees no smoking gun
   except a queue that's quietly growing.
6. `docker compose restart transcribe-md-worker` finally fixes it — but
   that's the brute-force fix. The detection lag is the real cost.

A healthcheck would have flagged the wedged container in 30 seconds, before
the doctor noticed anything.

## Recommended fix

Two complementary signals — pick both, since they catch different failure
modes:

1. **Liveness heartbeat**: have the worker write `bull:transcribe-md:alive`
   key with `EX 60` every 15 s. Add a sidecar healthcheck script invoked by
   Docker:
   ```dockerfile
   HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
     CMD node -e "require('ioredis').createClient(process.env.REDIS_URL).get('bull:transcribe-md:alive').then(v => process.exit(v ? 0 : 1))"
   ```
   Or simpler: `redis-cli -u $REDIS_URL get bull:transcribe-md:alive` (add
   `redis-cli` to the runner stage).

2. **Stuck-queue alarm**: extend `/api/health` to compare
   `bull:transcribe-md:wait` length against `transcribeVisit.findMany({
   where: { status: QUEUED, createdAt: { lt: 5 min ago } }})`. If the
   queue has waiting jobs older than 5 min, return a degraded signal —
   external monitor pages on-call.

Also add an explicit `process.on('unhandledRejection', err => {
   captureWorkerException(err, ...); process.exit(1) })` at the top of
`worker.ts` so a missed `await` kills the container instead of silently
deadlocking — which combined with `restart: unless-stopped` gives self-
healing within 10 seconds. (See also A11-P2-004.)
