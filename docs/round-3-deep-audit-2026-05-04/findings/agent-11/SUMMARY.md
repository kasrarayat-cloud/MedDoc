# Agent 11 — Error Handling & Observability · Summary

## Severity counts
**P0: 0 · P1: 6 · P2: 5 · P3: 3 · Total: 14**

## Top 3 findings
1. **A11-P1-001 — Sentry source maps NEVER uploaded.** `next.config.ts` does not call `withSentryConfig`, neither Dockerfile invokes `sentry-cli sourcemaps upload`, `SENTRY_RELEASE` is unbound. Every prod Sentry event arrives with minified stacks (`chunks/567-abc.js:1:12345`) — unactionable at 2 AM. Defeats the entire premise of having Sentry wired.
2. **A11-P1-002 — Redis runs default RDB-only (`appendonly no`)**, verified live (`docker exec redis-cli CONFIG GET appendonly` returns `no`). A crash/OOM/restart loses every BullMQ job enqueued since the last snapshot — visits stuck in `QUEUED`, audio orphaned in MinIO, no automatic recovery. Two-line `command:` change in compose buys ~1-second worst-case loss.
3. **A11-P1-003 — `transcribe-md-worker` has NO Docker healthcheck.** Most failure-prone service has zero liveness signal — wedged worker keeps reporting "running" while queue piles up. Combined with missing process-error handlers (A11-P2-002), realistic silent-failure mode for first 48 h of pilot.

## Other P1
- **A11-P1-004** — Single-provider transcription (Deepgram); no Whisper fallback, only retry-against-the-same-dead-provider.
- **A11-P1-005** — Marketing app has zero Sentry, zero `/api/health`, zero `error.tsx`, zero API routes — the public landing site is observability-blind.
- **A11-P1-006** — No BullMQ DLQ + no bull-board UI; failed jobs evict from a 500-entry rolling buffer; queue-failed cardinality not surfaced in `/api/admin/system/health`.

## Coverage
All 4 Sentry configs (client/server/edge/worker) read end-to-end · `instrumentation.ts` runtime dispatch verified · both Dockerfiles inspected for HEALTHCHECK + Sentry build wiring · `docker-compose.yml` healthcheck blocks per service + Redis runtime CONFIG verified live · Caddyfile scanned for `handle_errors` (absent) · structured-log wrapper (`apps/transcribe-md/src/lib/log.ts`) read in full; raw console.* enumerated (49 error/warn vs 57 structured `log.*`) · BullMQ retry/backoff/removeOnFail · worker pipeline catch-block + error-categorize + retry-decision logic · `withApiHandler` + `apiError` + rate-limit responses · marketing app full diff (no Sentry / no /api/health / no error.tsx). Out of scope as instructed: `apps/meddoc-pro/src/**`.

## Positives
1. **PHI scrubbing in Sentry is thoughtful** — every config's `beforeSend` calls `redactPhi()` over message+extra+breadcrumbs; edge config inlines the regex to stay edge-safe (`packages/ai/src/log.ts:67-90`).
2. **`/api/health` is genuinely useful** — races 2s timeout against postgres/redis/minio, no-store headers, APP_VERSION stamp, cleanup-cron heartbeat surface (`apps/transcribe-md/src/app/api/health/route.ts`).
3. **Worker error categorization is mature** — `error-categorize.ts` classifies transient/permanent/provider_down with a 60s sliding window; per-category reviewReason copy; retries skipped for permanent errors; T-M13 layer-skip resume preserves progress across retries.
4. **Per-attempt timeout (15min) + isolated cleanup queue** — stuck Anthropic/Deepgram call can't hold a worker slot indefinitely; long sweeps can't block visits; minute-bucketed jobIds for idempotent re-enqueue.
5. **`withApiHandler` + `apiError` provide consistent JSON failure shape** with `{code, retry}` taxonomy; MinIO permanent-vs-transient classification; queue-unreachable returns 502 with retry hint + audio preserved.

## Cross-domain hooks
- **Agent 05** (PHI/HIPAA): A11-P1-001 (no source maps) means hypothetical PHI in column-value positions in stack traces; A11-P3-003 (no header/cookie/secret middleware) is preventive hygiene.
- **Agent 02** (auth): A11-P2-004 (no Sentry setUser) needs auth-side hook to plumb userId.
- **Agent 06** (pipeline): A11-P1-004 (no Deepgram fallback) is pipeline-resilience — coordinate Whisper-vs-internal-queue ranking.
- **Agent 07** (Caddy/network): A11-P2-003 (Caddy `handle_errors`) touches Caddyfile.
- **Agent 12** (final integration): A11-P1-002 + A11-P1-003 are compose/Dockerfile changes — coordinate with the regression matrix in MEMORY (9-container layout, expected health responses) so worker heartbeat key (`bull:transcribe-md:alive`) gets a row.
