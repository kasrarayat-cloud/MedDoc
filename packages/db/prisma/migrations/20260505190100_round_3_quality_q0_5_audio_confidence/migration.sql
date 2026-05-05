-- Round 3 quality fix-pack Q0-5 — propagate Deepgram per-utterance
-- confidence through the pipeline.
--
-- Closes audit findings:
--   07.3 — Deepgram per-utterance confidence is captured but not
--          propagated to L2/L3/L4/L5; downstream layers treat the
--          transcript as ground truth regardless of audio fidelity.
--   02.5 — Heavy accent / mumbling produces overconfident SOAPs;
--          there is no fail-closed signal to the doctor that the
--          SOAP is built on garbled input.
--
-- Schema delta: a single nullable JSONB column on transcribe_visits.
-- L1 (01-transcribe.ts + 01b-transcribe-dictation.ts) writes this
-- after each batch returns; the worker threads the stats into L4 and
-- L5 input so the prompts can hedge language when audio fidelity is
-- low. Null is the legitimate value for text_notes (no audio) and
-- for L1b runs where utterance segmentation is disabled.

ALTER TABLE "transcribe_visits"
ADD COLUMN "audioConfidenceStats" JSONB;
