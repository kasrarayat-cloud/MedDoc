-- F5-f ruling 2(b): a signed record resolves its document by POINTER, never by
-- lookup, so a manifest landing after the signature is unreachable.
--
-- NULLABLE: null means "signed styled", a deliberate recorded outcome. Existing
-- signed visits keep null and therefore serve styled — correct, because nothing
-- proves which manifest (if any) their signature actually froze.
ALTER TABLE "transcribe_visits"
  ADD COLUMN "frozenFillManifestId" TEXT;

ALTER TABLE "transcribe_visits"
  ADD CONSTRAINT "transcribe_visits_frozenFillManifestId_fkey"
  FOREIGN KEY ("frozenFillManifestId")
  REFERENCES "template_twin_fill_manifests"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;

-- Declared in schema.prisma in this same commit (no drift).
CREATE INDEX "transcribe_visits_frozenFillManifestId_idx"
  ON "transcribe_visits"("frozenFillManifestId");
