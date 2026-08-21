-- F5-f ruling 1: a fill manifest is servable only when it PROVABLY corresponds
-- to the visit's current note.
--
-- NULLABLE by design. Manifests written before this column cannot prove which
-- note they were filled from, so the serve path must DECLINE them rather than
-- trust them. Backfilling a guess would be worse than the defect: it would make
-- an unprovable artifact look proven.
ALTER TABLE "template_twin_fill_manifests"
  ADD COLUMN "noteSha256" CHAR(64);
