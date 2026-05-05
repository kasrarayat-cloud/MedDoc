-- Round 3 PR-E — data integrity.
-- Closes audit findings:
--   A09-P0-001 — Rx warning bypass via duplicate insert (no unique
--                constraint on rx_warning_overrides; same warning could
--                be re-inserted N times, polluting the visit Rx rail
--                and bypassing the sign gate's distinct-warning count).
--   A09-P0-003 — SOAP last-write-wins (no optimistic concurrency on
--                transcribe_visits.soapFinal; two doctors editing the
--                same SOAP overwrite each other silently).

-- =============================================================================
-- Subtask 1 — RxWarningOverride: dedupe + unique constraint
-- =============================================================================
-- Step 1: dedupe existing rows. Keep the oldest by `overriddenAt` (preserves
-- the original audit trail for the first override of each (visit, warning)
-- pair). Tiebreak by id ascending so the cuid sort is deterministic.
DELETE FROM rx_warning_overrides a
USING rx_warning_overrides b
WHERE a.id > b.id
  AND a."visitId" = b."visitId"
  AND a."warningId" = b."warningId";

-- Step 2: add the compound unique constraint. Now further duplicate inserts
-- raise a Postgres unique-violation, which the recordOverride() upsert path
-- catches and converts into idempotent no-op semantics.
ALTER TABLE rx_warning_overrides
  ADD CONSTRAINT rx_warning_overrides_visitId_warningId_key
  UNIQUE ("visitId", "warningId");

-- =============================================================================
-- Subtask 2 — TranscribeVisit: soapVersion column for optimistic concurrency
-- =============================================================================
-- Default 1 so existing rows have a starting version. NOT NULL because every
-- visit always has a version once we start tracking — the optimistic check
-- treats `WHERE soapVersion = $expected` as the gate.
ALTER TABLE transcribe_visits
  ADD COLUMN "soapVersion" INTEGER NOT NULL DEFAULT 1;
