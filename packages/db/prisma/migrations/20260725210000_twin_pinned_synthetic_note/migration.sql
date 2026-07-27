-- Pinned synthetic note — makes certification DETERMINISTIC.
--
-- The synthetic proof ran the live L4 on every attempt, so which sections the
-- model emitted varied run to run: one run filled the DIAGNOSIS control, the
-- next left it NEEDS_CLINICIAN_INPUT and blocked. A certificate whose outcome
-- depends on a sampling decision is not a certificate.
--
-- The note is now generated ONCE (through the real ephemeral-visit path) and
-- pinned. Certification then consumes the pinned note through the full
-- production machinery — bridge, matcher, validator, renderer, roundtrip —
-- so nothing is bypassed; only the stochastic INPUT is fixed.
--
-- Re-pin triggers are the two hashes: a changed encounter or a changed
-- template invalidates the pin, plus an explicit operator re-pin.
--
-- Additive only: five nullable columns, no backfill, no constraint changes.
-- ROLLBACK: drop the five columns; an unpinned template simply generates again.
ALTER TABLE "template_twin_compiled_versions"
  ADD COLUMN "pinnedSyntheticNote"       TEXT,
  ADD COLUMN "pinnedNoteEncounterSha256" CHAR(64),
  ADD COLUMN "pinnedNoteTemplateSha256"  CHAR(64),
  ADD COLUMN "pinnedNoteModelVersion"    TEXT,
  ADD COLUMN "pinnedNoteGeneratedAt"     TIMESTAMPTZ(6);
