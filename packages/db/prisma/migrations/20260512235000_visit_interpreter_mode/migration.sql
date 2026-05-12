-- Interpreter-mode columns on TranscribeVisit (Sylvia incident follow-up).
--
-- The Kasra stuck-visit incident exposed that the English-only
-- nova-3-medical Deepgram model captures only the clinician's questions
-- when run against a multi-language interpreted visit (Spanish patient
-- + English doctor + Spanish interpreter). The fragmentary transcript
-- can't produce a usable SOAP.
--
-- Two new columns:
--   - interpreterMode  — set at visit creation by the "With
--                        interpreter?" checkbox. Drives L1 model
--                        choice + L2/L4 prompt branches.
--   - detectedLanguage — populated by L1's detect_language pass on
--                        interpreter-mode visits. Reserved for a
--                        future soft-banner that offers to reprocess
--                        an English-flagged visit in interpreter mode
--                        if the model detected non-English content.

ALTER TABLE "transcribe_visits"
  ADD COLUMN IF NOT EXISTS "interpreterMode" BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS "detectedLanguage" TEXT;
