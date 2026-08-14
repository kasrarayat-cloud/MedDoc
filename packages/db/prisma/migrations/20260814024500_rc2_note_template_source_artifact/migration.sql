-- ===========================================================================
-- RC-2 — THE UPLOADED TEMPLATE FILE IS A KEPT ARTIFACT.
-- Ruling #106(b), SPEC §4.3a(e). Two nullable columns; no backfill, no data.
-- ---------------------------------------------------------------------------
-- WHAT THIS REPAIRS
--
-- Every `.docx` uploaded through Settings → My Note Format had its text
-- extracted and its BYTES DISCARDED — `extract-note-file.ts` held the buffer in
-- memory, returned a string, and let it go. `note_templates` had nowhere to put
-- a reference even if somebody had wanted to keep one.
--
-- The consequence is the one part of #106 that cannot be undone by any amount
-- of later code: a customer's logo and letterhead stopped existing at upload.
-- They are recoverable from nothing we hold, and the fix cannot bring them
-- back — it can only stop the next one.
--
-- ⚠️ NULLABLE, WITH NO BACKFILL, AND THE NULL MEANS SOMETHING PRECISE.
-- NULL = "we do not have this template's file". That is true of every row
-- created before this migration, and of every template created by PASTE rather
-- than upload — which remains a first-class path. A future reader must not
-- read NULL as "the file is somewhere else"; there is no somewhere else.
--
-- ⚠️ NO DEFAULT, DELIBERATELY. A default would make "never had a file" and
-- "file not yet linked" indistinguishable at exactly the moment somebody is
-- trying to tell them apart.
--
-- Both columns are additive and nullable, so this migration cannot fail on
-- existing data and needs no abort guard — the class of guard RC-1's
-- reclassification required does not apply to a pure ADD COLUMN.
-- ===========================================================================

ALTER TABLE "note_templates" ADD COLUMN "sourceObjectKey" TEXT;
ALTER TABLE "note_templates" ADD COLUMN "sourceSha256" TEXT;

-- ⚠️ NO INDEX, AND THE OMISSION IS CONSIDERED. Nothing looks a template up BY
-- its object key; the key is read FROM a row already found by id. Adding an
-- index nobody queries would be undeclared drift of exactly the kind
-- AGENTS.md's schema-drift rule exists to prevent — an object in the database
-- that the schema does not declare and no code needs.
