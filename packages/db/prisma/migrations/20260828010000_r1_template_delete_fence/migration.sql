-- ===========================================================================
-- R1 — THE HARD-DELETE FENCE. A PROVENANCE COLUMN IS NEVER `ON DELETE SET NULL`.
-- ---------------------------------------------------------------------------
-- ⚠️ WHAT THIS REPAIRS, MEASURED BEFORE IT WAS WRITTEN.
--
-- `transcribe_visits.noteTemplateId` is the provenance link from a clinical
-- note to the template it was written against. Its FK carried
-- `ON DELETE SET NULL`, so deleting a template SILENTLY ERASED that link on
-- every visit bound to it — including SIGNED medical records — with no warning,
-- no audit row, and no way to tell an erased binding from a note that never had
-- one.
--
-- Census on production the day this landed:
--
--     total visits                                     52
--     provenance DESTROYED (id NULL, version still 1)  29   ← 56% of the corpus
--     of those SIGNED                                  18
--     genuinely untemplated (both columns NULL)         2
--
-- The (NULL id, SET version) pair is unwritable by any code path — every writer
-- sets the two columns together — so the FK cascade is the only thing that can
-- produce it. That is how the 29 were identified.
--
-- ⚠️ NO SIGNED RECORD IS BROKEN TODAY, and this migration does not pretend
-- otherwise: all 18 still serve, because none of them carried a frozen fill
-- manifest for the cascade to reach (production holds 2 manifests in total, both
-- pointing at a template that still exists; dangling frozen refs = 0). What they
-- lost is their EXPORT CONFIG — `visit-export-server.ts:75` reads headerFields /
-- formOnlyExport / section labels THROUGH this relation, so a nulled link
-- degrades the doctor's own form to generic chrome. Served, degraded, not
-- broken. The fence is urgent for the next deletion, not for these.
--
-- ⚠️ THIS MIGRATION REPAIRS NOTHING RETROACTIVELY, DELIBERATELY. The 29 existing
-- rows are left exactly as they are. Restoring provenance would mean guessing
-- which template each visit used, and the evidence cannot identify one: only 2
-- source artifacts survive against 18 signed orphans, `version` is uniformly 1,
-- and the heading-shape fingerprint is a SHAPE not a SIGNATURE (the same six
-- operative headings belong to three surviving templates owned by a different
-- doctor). Attribution by inference must never be written into a signed record.
-- The recovery act is a separately authorised, append-only AUDIT ANNOTATION.
--
-- ---------------------------------------------------------------------------
-- WHY RESTRICT AND NOT CASCADE.
-- CASCADE would delete the visits — destroying clinical records to satisfy a
-- referential rule, which is the worse failure by far. RESTRICT refuses the
-- delete and keeps both sides. The application refuses first, with a readable
-- message; this constraint is the floor under that, for every path that does not
-- go through the action (a script, a console, a future writer).
-- ===========================================================================

ALTER TABLE "transcribe_visits"
  DROP CONSTRAINT IF EXISTS "transcribe_visits_noteTemplateId_fkey";

ALTER TABLE "transcribe_visits"
  ADD CONSTRAINT "transcribe_visits_noteTemplateId_fkey"
  FOREIGN KEY ("noteTemplateId") REFERENCES "note_templates"("id")
  ON UPDATE CASCADE ON DELETE RESTRICT;
