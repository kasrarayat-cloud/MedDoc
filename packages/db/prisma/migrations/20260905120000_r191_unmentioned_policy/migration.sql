-- RULING #192 — `unmentionedPolicy` is a per-field DECLARATION, and its absence
-- is a MEANING, not a missing value.
--
-- ⚠️ NULLABLE WITH NO DEFAULT, AND THAT IS THE WHOLE CORRECTION. #191 shipped
-- this as `TEXT NOT NULL DEFAULT 'keep'`, which was right while `keep` and
-- absent were semantically identical. #192 makes them OPPOSITES: absent is
-- today's bounded clear (fail-closed — a prompt can never print), `keep` keeps
-- the doctor's own clause. A `DEFAULT 'keep'` would therefore have silently
-- opted EVERY EXISTING MAPPING into keeping, and printed template prompts onto
-- notes nobody re-certified.
--
-- ⚠️ AND IT IS WHAT KEEPS EVERY CERTIFIED SHA STILL. `templateTwinMappingsSha256`
-- hashes the mapping; `fill-engine` throws TEMPLATE_PROVENANCE_MISMATCH when it
-- moves. Pre-existing rows are NULL and contribute NOTHING to the hash, so no
-- certification breaks — while both explicit values DO move it, which is
-- correct, because each is a declaration that changes what the document says.
--
-- The #191 form of this migration was never applied in any environment.
ALTER TABLE "template_twin_semantic_mappings"
  ADD COLUMN "unmentionedPolicy" TEXT;
