-- 2026-05-13 Issues #202 + #206 — keyterm composition audit field.
-- Stores per-visit metadata about which keyterms were sent to
-- Deepgram so a future transcription regression can be attributed
-- to the exact composition that ran. Shape documented at
-- `apps/transcribe-md/src/lib/deepgram-keyterm-builder.ts`.

ALTER TABLE "transcribe_visits"
  ADD COLUMN IF NOT EXISTS "keytermsApplied" JSONB;
