---
id: A11-P1-002
severity: P1
domain: error-handling-observability
title: Redis runs default RDB-snapshot only — no AOF, BullMQ jobs lost on container crash
---

# A11-P1-002 — Redis has no AOF persistence; in-flight BullMQ jobs are lost on a Redis OOM/restart

## Issue

`docker-compose.yml` runs the bare `redis:7-alpine` image with **no `command:`
override** and no Redis config file mounted. The runtime config is therefore
the image default: RDB snapshot every `3600s/1key, 300s/100keys, 60s/10000keys`
and **`appendonly no`**.

BullMQ persists every job (queued / active / failed / delayed / completed) in
Redis lists + hashes. With AOF disabled, the only durability surface is the
periodic RDB dump. If Redis OOMs, the host reboots, or the container is
recreated mid-snapshot-window (we verified `mem_limit: 128m` on this service —
a single noisy queue + Lua state has plausibly hit that ceiling already),
**every job that arrived since the last snapshot is gone**, including:

- `transcribe-md` queue: visits in the audio pipeline. A doctor's recording is
  in MinIO, the visit row is `QUEUED`, but no worker will ever pick it up —
  the visit will sit forever.
- `transcribe-md-cleanup` queue: scheduled MinIO orphan / stale-visit /
  retention sweeps will silently miss a window.

This is on top of the other persistence trap: the `redis_data` named volume
is fine, but with `appendonly no` + RDB-only, `BGSAVE` only fires after the
trigger conditions accumulate. A crash 50 seconds after a flurry of upload
enqueues = those jobs are gone.

## Evidence

`docker-compose.yml:136-158`:
```yaml
redis:
  image: redis:7-alpine
  restart: unless-stopped
  ...
  mem_limit: 128m
  ...
  volumes:
    - redis_data:/data
  ...
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
```
No `command:`. No bind-mounted `redis.conf`.

Live runtime check (5.231.107.93 prod container):
```
$ docker exec <redis> redis-cli CONFIG GET appendonly
appendonly
no

$ docker exec <redis> redis-cli CONFIG GET save
save
3600 1 300 100 60 10000
```

`apps/transcribe-md/src/lib/queue.ts:46-66` — `defaultJobOptions: { attempts: 3,
backoff: { type: 'exponential', delay: 5_000 } }`. Retries are useless if the
job record itself never made it to disk.

## Risk

A real production incident path:
1. Doctor uploads a 45-min recording → `audio` lands in MinIO, visit row =
   `QUEUED`, job hits Redis at 14:30:05.
2. Redis hits its 128 MB ceiling at 14:30:30 (or VPS swap pressure, or any
   `docker compose down`).
3. Container restarts; `redis_data` volume is intact but only contains a
   `dump.rdb` from 14:00 (last RDB trigger).
4. The job ID is gone. BullMQ workers idle on an empty queue. The visit is
   stuck in `QUEUED` forever.
5. The doctor returns the next morning expecting a SOAP draft, sees a stuck
   spinner, contacts support. Support has no way to detect the stuck-queue
   state without an explicit cron/health probe (see A11-P2-001 — there isn't
   one for queue depth vs visit row count).

This is also a HIPAA durability / availability concern — the BAA promises
the doctor's audio is processed; if it silently disappears, that's
data-handling failure.

## Recommended fix

Two-line change in `docker-compose.yml`:
```yaml
redis:
  image: redis:7-alpine
  command:
    - redis-server
    - --appendonly
    - "yes"
    - --appendfsync
    - "everysec"
    - --maxmemory
    - "96mb"
    - --maxmemory-policy
    - "noeviction"
```

- `appendonly yes` + `appendfsync everysec` → at most 1 second of in-flight
  job loss on a hard crash, vs. up to an hour today.
- `maxmemory 96m` + `noeviction` → fail-loud (OOM error returned to client,
  caller can retry the enqueue) instead of silently evicting random BullMQ
  job hashes which would be much worse.
- Keep `mem_limit: 128m` as the cgroup ceiling so the container has 32 MB
  headroom over Redis's own maxmemory.

Also add to the launch checklist: after deploy, verify
`redis-cli CONFIG GET appendonly` returns `yes`. Document AOF rewrite
sizing + rotation in DEPLOYMENT_RUNBOOK.md (default
`auto-aof-rewrite-percentage` 100 / `auto-aof-rewrite-min-size 64mb` is fine
but make it explicit).
