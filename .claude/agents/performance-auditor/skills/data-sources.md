# Data sources — Performance Auditor

> The agent reads only the sources documented here. Adding a new
> source requires updating this doc + bumping the agent's version.

## §1 · Postgres (read-only)

| Table | Columns read | Why |
|---|---|---|
| `transcribe_visits` | `id`, `userId`, `practiceId`, `uploadedAt`, `processedAt`, `status`, `inputMode`, `audioDurationSec`, `dictationDurationSec`, `deletedAt`, `archivedAt` | Pipeline RTT, per-mode rollups, deleted/archived filtering. |
| `audit_logs` | `action`, `timestamp`, `metadata` (only the timing key if present) | Server-side timing markers, when emitted by `withApiHandler`. |
| `ai_calls` | `layerName`, `latencyMs`, `successAt`, `failedAt` | Per-layer latency rollups (read-only; same pattern as ai-pipeline-auditor uses). |

**PHI columns explicitly NOT read:** `transcript`, `soapDraft`,
`soapFinal`, `icdCodes`, `rxDrafts`, `cptCodes`, `patientName`,
`patientDob`, `audioMinioKey`. The auditor's queries `SELECT` only
the columns above; never `SELECT *`.

## §2 · Redis (read-only)

| Key pattern | Operation | Why |
|---|---|---|
| `bull:transcribe-md:waiting` | `SCARD` | Queue depth. |
| `bull:transcribe-md:active` | `SCARD` | Workers currently processing. |
| `bull:transcribe-md:delayed` | `SCARD` | Scheduled retries. |
| `bull:transcribe-md-dlq:waiting` | `SCARD` | Dead-letter depth. |
| `bull:transcribe-md:completed` | `SCARD` | Completed (sanity check). |
| `bull:transcribe-md:failed` | `SCARD` | Failed-but-not-yet-DLQ (transient). |

**Job payloads explicitly NOT read** — `LRANGE` / `HGETALL` are
not used. The auditor reads cardinalities only. Job payloads
contain visitId references that could be cross-referenced to
PHI; reading the cardinality stays in safe territory.

## §3 · Filesystem (read-only)

| File | Why |
|---|---|
| `apps/transcribe-md/.next/app-build-manifest.json` | Per-route bundle composition for size delta. |
| `apps/transcribe-md/.next/build-manifest.json` | Top-level bundle entries. |
| `.claude/agents/performance-auditor/fixtures/*.json` | Baseline tables for percentage-drift comparison. |

## §4 · Diffs (PR-time mode only)

| Source | Why |
|---|---|
| `gh pr diff <N>` | Prisma N+1 static analysis. |
| `git diff` (uncommitted) | Same, against the working tree. |

## What I do NOT read

- Transcript text / SOAP body / patient identifiers (any).
- Job payloads in BullMQ (`LRANGE` / `HGETALL` are not used).
- The MinIO bucket contents (audio / image files).
- The Next.js build's `.html` artifacts (no rendered route content).
- The production VPS's `/var/log/**` (operator-owned territory).
- Any column not listed in §1.

## Defense-in-depth Postgres role (planned)

`performance_auditor` Postgres role with `SELECT` on the columns in
§1 and `USAGE` on the relevant schemas. Even though every query is
SELECT, enforcing it at the role level is the right defense-in-
depth — a typo in a future query that accidentally writes fails
immediately.

Connection string lives in `/opt/meddoc-pro/.env` as
`PERFORMANCE_AUDITOR_DATABASE_URL` (not committed). Provisioning
this role is part of graduation, not shadow mode — shadow runs
use the operator's interactive session credentials.
