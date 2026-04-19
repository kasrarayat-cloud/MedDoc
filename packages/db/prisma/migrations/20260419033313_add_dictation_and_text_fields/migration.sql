-- T-M5: voice dictation + text-to-SOAP input columns.
-- All additive + nullable; no data migration needed.
ALTER TABLE "transcribe_visits"
  ADD COLUMN "dictationAudioKey"    TEXT,
  ADD COLUMN "dictationDurationSec" INTEGER,
  ADD COLUMN "rawTextInput"         TEXT;
