-- A mapping-rule correction creates a new immutable NoteTemplate version
-- while deliberately reusing the original, immutable source artifact and IR.
-- The original uniqueness constraint incorrectly prevented that lineage fork.
DROP INDEX IF EXISTS "template_twin_compiled_source_compiler_key";

CREATE INDEX "template_twin_compiled_versions_sourceArtifactId_compilerVersion_idx"
  ON "template_twin_compiled_versions"("sourceArtifactId", "compilerVersion");
