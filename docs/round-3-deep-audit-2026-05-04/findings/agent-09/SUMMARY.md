# Agent 09 — Data Integrity & Race Conditions · Summary

## Severity counts
**P0: 3 · P1: 4 · P2: 4 · P3: 2 · Total: 13**

## Top 3 findings
1. **A09-P0-001 — Rx critical-warning sign gate bypassable.** Sign uses `rxWarningOverride.count()` over `(visitId, severity)` instead of distinct-warningId coverage. No `@@unique([visitId, warningId])` on the model, no dedupe in `recordOverride()`. Doctor double-clicks override on warning A → count=2 satisfies criticalWarnings.length=2 → warning B silently waved through. Patient safety + clinical-audit defect.
2. **A09-P0-002 — `audit_logs` is application-mutable.** No `REVOKE … ON audit_logs FROM meddoc` anywhere in `packages/db/`, `infra/`, or `scripts/`. App role can DELETE/UPDATE the HIPAA audit table. §164.312(b) technical safeguard missing.
3. **A09-P0-003 — SOAP save is last-write-wins.** `saveSoapDraftAction` does findUnique + unconditional `update`. No `version`/`updatedAt` predicate. Two-tab edit silently destroys one tab's changes.

## Other findings
- P1-001 No worker claim/lease lock (re-enqueue race could double-process)
- P1-002 Soft-delete + restore race
- P1-003 Backup-chain races (cron starts before sidecar completes)
- P1-004 Cleanup sweep race vs in-flight worker
- P2-001 Non-atomic upload + state-set
- P2-002 No idempotency keys on outbound (Resend, Anthropic)
- P2-003 Text-edit race between SSE fan-out and writer
- P2-004 Webhook handlers (Resend) replay-not-safe in places
- P3-001 Distributed-lock pattern absent for cron + worker
- P3-002 No Redis SETNX lock pattern (post-pilot horizontal scale concern)

## Coverage
Read full `apps/transcribe-md/src/worker.ts` (1087 lines), every `worker/{layers,cleanup,prompts}/*.ts`, all server actions, every state-changing API route under `app/api/{visits,settings,auth,patients}/`, full TranscribeVisit/AuditLog/AccountDeletion/RxWarningOverride schemas, all destructive DDL in migrations/, the postgres-offsite + minio-offsite + backup-offsite-sync scripts, and the postgres-backup compose service. No sampling.

## Positives
1. `/sign` route correctly uses `updateMany({ where: { id, status: READY }})` atomic compare-and-swap with explicit race-loss handling — the only state transition done correctly; reference for fixing the others.
2. `signup` and `delete-account` both use `prisma.$transaction(async tx => …)` with sensible rollback; audit row written OUTSIDE the destructive tx with explicit userId so post-cascade session loss doesn't lose the compliance record.
3. Cleanup sweeps (`worker/cleanup/stale-visits.ts:71-78`) wrap multi-step `aiCall.deleteMany + transcribeVisit.deleteMany` in a transaction; MinIO best-effort runs AFTER commit so rollback doesn't strand objects.
4. T-M13 per-layer resume — checkpoint columns mean retries skip completed layers.
5. Queue `removeOnComplete: { count: 500, age: 24 * 3600 }` — bounded Redis retention.

## Cross-domain hooks
- **P0-001 → Agent 05/06** (audit lineage validation, clinical safety)
- **P0-002 → Agent 05/12** (HIPAA + DB role bootstrap, not just Prisma)
- **P1-001 → Agent 11** (cost; alert on duplicate-cost spikes)
- **P1-002 → Agent 10** (UX needs Cancel vs Delete distinction)
- **P1-003 → Agent 07/12** (infra + DR/RPO)
- **P2-002 → Agent 11** (cost containment)
- **P2-001/003 → Agent 04** (worker claim is upstream fix)
- **P3-002 → Agent 07** (post-pilot horizontal scaling)
