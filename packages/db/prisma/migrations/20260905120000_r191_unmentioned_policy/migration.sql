-- Ruling #191 — the scaffolded-field policy.
--
-- For a SCAFFOLDED control (non-empty default content at compile), what happens
-- when no fact matches: `keep` leaves the doctor's own clause standing and earns
-- `default_kept` (which requires a citation, so a field nobody evaluated cannot
-- reach it); `omit` clears it through the proven bounded clear.
--
-- DEFAULT 'keep' IS DELIBERATE AND IS WHY THIS IS BACKWARD-COMPATIBLE. Existing
-- rows take 'keep', and `default_kept` requires a non-empty citation, so any
-- mapping that evaluated no facts still falls through to today's behaviour.
-- Nothing rendered today changes.
--
-- NOT NULL with a default, so the column is safe on a populated table and no
-- write path can leave it unset.
ALTER TABLE "template_twin_semantic_mappings"
  ADD COLUMN "unmentionedPolicy" TEXT NOT NULL DEFAULT 'keep';
