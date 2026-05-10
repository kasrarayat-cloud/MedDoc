# Finding classes — Performance Auditor

> Five severity tiers. The first three are operationally critical
> (`BLOCKING_*`); they should be acted on regardless of shadow vs
> production status. The bottom two are advisory.

## Severity tiers

| Tier | Meaning | Examples |
|---|---|---|
| `BLOCKING_OUTAGE` | System is broken or about to break. | DLQ depth > 100; queue stuck > 30min; pipeline RTT p99 > 30min over last hour. |
| `BLOCKING_REGRESSION` | Performance regressed materially against baseline. | Pipeline RTT p95 > 2× baseline over last 24h; route TTFB p95 > 3× baseline. |
| `BLOCKING_BUDGET` | Hard budget exceeded. | Bundle size for `/visits/[id]` > 250KB (Linear-V1 budget). |
| `WARN_DRIFT` | Performance drifted but not catastrophically. | Pipeline RTT p95 > 1.3× baseline; queue waiting depth > 50 over 5 minutes. |
| `INFO_TREND` | Trend worth noting; no action required. | Day-over-day change >10%; bundle size grew but stayed under budget. |

## Per-phase finding classes

### Phase 1 — Pipeline RTT

| Class | Trigger | Tier |
|---|---|---|
| `PIPELINE_RTT_OUTAGE` | p99 over last 1h > 30min | BLOCKING_OUTAGE |
| `PIPELINE_RTT_REGRESSION` | p95 over last 24h > 2× baseline | BLOCKING_REGRESSION |
| `PIPELINE_RTT_DRIFT` | p95 over last 24h > 1.3× baseline | WARN_DRIFT |
| `PIPELINE_RTT_PER_MODE` | per-mode (audio_conversation / voice_dictation) p95 differs from rollup by > 50% | INFO_TREND |

### Phase 2 — Queue + DLQ

| Class | Trigger | Tier |
|---|---|---|
| `DLQ_FLOOD` | DLQ depth > 100 | BLOCKING_OUTAGE |
| `DLQ_NONZERO` | DLQ depth > 0 | WARN_DRIFT (the operator should always look at any DLQ entry) |
| `QUEUE_BACKLOG` | Waiting depth > 50 sustained > 5 minutes | WARN_DRIFT |
| `QUEUE_HEALTHY` | All depths < 10 | INFO_TREND (positive signal — included in shadow report's summary) |

### Phase 3 — Prisma N+1 (PR-time)

| Class | Trigger | Tier |
|---|---|---|
| `N_PLUS_1_LOOP_AWAIT` | `for (const x of xs) { await prisma.y.findUnique(...) }` or analogous patterns in PR diff | BLOCKING_REGRESSION |
| `N_PLUS_1_MAP_AWAIT` | `Promise.all(xs.map(x => prisma.y.findUnique(...)))` over a list of length > expected (e.g. `Promise.all(visits.map(v => prisma.user.findUnique({where: {id: v.userId}})))` — fixable via `findMany({where: {id: {in: ...}}})`) | WARN_DRIFT |

### Phase 4 — Route TTFB

| Class | Trigger | Tier |
|---|---|---|
| `TTFB_OUTAGE` | p95 > 5s over last 1h | BLOCKING_OUTAGE |
| `TTFB_REGRESSION` | p95 > 3× baseline over last 24h | BLOCKING_REGRESSION |
| `TTFB_DRIFT` | p95 > 1.5× baseline over last 24h | WARN_DRIFT |

### Phase 5 — Bundle size

| Class | Trigger | Tier |
|---|---|---|
| `BUNDLE_BUDGET_EXCEEDED` | `/visits` or `/visits/[id]` route > 250KB after gzip | BLOCKING_BUDGET |
| `BUNDLE_DELTA_LARGE` | Route bundle grew > 25KB vs baseline in a single PR | WARN_DRIFT |
| `BUNDLE_DELTA_SMALL` | Bundle grew 5-25KB | INFO_TREND |

## How shadow handles severity

Shadow does NOT downgrade. A `BLOCKING_OUTAGE` finding in a shadow
report is still a `BLOCKING_OUTAGE` and should trigger immediate
operator action — shadow only relocates the report to
`docs/agent-shadow-runs/performance/<UTC>.md` instead of a
production-blocking path.

This mirrors the HIPAA Compliance Auditor's contract: severity is
preserved across shadow → production transitions; only the
report's audience-and-coupling moves.
