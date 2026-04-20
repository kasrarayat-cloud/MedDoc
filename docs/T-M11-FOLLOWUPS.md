# T-M11 — deferred follow-ups (historical log)

The T-M11 error-hardening pass flagged four worker-side improvements. Two landed in T-M11 itself (per-job 15-min timeout, audit rollup); two were deferred and **both have since shipped**. This file is kept as a historical record — do not use it for current planning, it's frozen at T-M13.

---

## 1. Per-layer pipeline resumability — **shipped in T-M13** ✓

Merged 2026-04-20 (PR #24).

**Was the problem**: if Layer 6 (polish) threw, the BullMQ retry re-ran Layers 1-5 from scratch — re-hitting Deepgram for Layer 1 and re-prompting Claude for Layers 2-5. A single failed visit could cost ~2× the normal spend per retry (up to 3× at max attempts).

**How T-M13 solved it**: `apps/transcribe-md/src/worker/layer-skip.ts` maps each pipeline layer to a column-presence check on the TranscribeVisit row. `isLayerComplete(visit, 'L4')` returns true when the column that layer writes to is already populated, so retries skip ahead to the first empty slot. Unit tests at `apps/transcribe-md/tests/worker/layer-skip.test.ts` cover each layer + mid-pipeline-failure resume paths.

## 2. MinIO orphan cleanup — **shipped in T-M12** ✓

Merged 2026-04-20 (PR #23).

**Was the problem**: `/api/visits/[id]/upload` wrote bytes to MinIO under `{userId}/{visitId}/…`. If a visit row later disappeared (test cleanup, HIPAA retention), the MinIO object orphaned. Bucket grew monotonically.

**How T-M12 solved it**: a scheduled sweep in `apps/transcribe-md/src/worker/cleanup/minio-orphans.ts` lists MinIO objects, cross-checks against `transcribe_visits.audioKey` / `dictationAudioKey`, and deletes objects older than `MINIO_ORPHAN_CLEANUP_RETENTION_DAYS` (default 30) that no row references. Gated behind `MINIO_ORPHAN_CLEANUP_ENABLED` (default false) with a separate `MINIO_ORPHAN_CLEANUP_DRY_RUN` flag for audited first-run visibility. Cron schedule is env-configurable. Full details in `docs/T-M12-MINIO-CLEANUP.md`.

---

## Where to file new follow-ups

Post-T-M14.1, the active follow-up log is `docs/T-M15-AUDIT-REPORT.md`, which catalogs ~40 findings from the pre-launch QA audit. T-M16 subtasks are scoped from that report.
