-- T-M6: add AUTOMATING state to TranscribeVisitStatus enum.
-- Placed AFTER POLISHING so the enum's display-order matches the
-- pipeline's flow: QUEUED → TRANSCRIBING → EXTRACTING → DRAFTING →
-- CRITIQUING → POLISHING → AUTOMATING → READY.
ALTER TYPE "TranscribeVisitStatus" ADD VALUE 'AUTOMATING' AFTER 'POLISHING';
