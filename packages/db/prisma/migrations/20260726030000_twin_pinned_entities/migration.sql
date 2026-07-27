-- Pinned synthetic ENTITIES — the other half of a deterministic certification.
--
-- The note was pinned so the generator's sampling could not decide the outcome.
-- But the synthetic test also re-ran Layer 3 on every attempt, and L3 is a model
-- too: run to run it returned different facts for the identical encounter text,
-- so the same template blocked on a different set of fields each time. A
-- certificate whose outcome depends on two sampling decisions is no more a
-- certificate than one that depends on one.
--
-- With the extraction pinned, the whole synthetic proof is a pure function of
-- (source document, encounter text). The pinned entities still flow through
-- projection -> resolver -> bridge -> matcher -> validator -> renderer ->
-- roundtrip exactly as freshly extracted ones would: only the stochastic INPUT
-- is fixed, and no requirement is relaxed.
--
-- Keyed by the SAME encounter hash the note pin uses, so the two invalidate
-- together. PHI-safe: the encounter is synthetic by gate (it must carry an
-- explicit synthetic marker and pass the PHI screen before anything is stored).
--
-- Additive only: two nullable columns, no backfill, no constraint changes.
-- ROLLBACK: drop the two columns; certification simply extracts again per run.
ALTER TABLE "template_twin_compiled_versions"
  ADD COLUMN "pinnedSyntheticEntities"    JSONB,
  ADD COLUMN "pinnedSyntheticContextText" TEXT;
