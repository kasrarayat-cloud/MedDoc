-- T-M4: audio → SOAP pipeline fields.
-- Hand-written rather than prisma-generated because the status column
-- needs an in-place String → enum conversion with a data migration
-- (existing rows carry the T-M2 default "draft"; the prisma auto-diff
-- would DROP + re-ADD the column and lose that history).

-- ── 1. New enum. All 9 pipeline states up front so downstream layers
--      can enqueue transitions without a future migration. ──
CREATE TYPE "TranscribeVisitStatus" AS ENUM (
  'QUEUED',
  'TRANSCRIBING',
  'EXTRACTING',
  'DRAFTING',
  'CRITIQUING',
  'POLISHING',
  'READY',
  'FAILED',
  'SIGNED'
);

-- ── 2. Additive columns for the pipeline. All nullable or with safe
--      defaults so existing rows are happy. ──
ALTER TABLE "transcribe_visits"
  ADD COLUMN "audioMimeType"        TEXT,
  ADD COLUMN "audioSizeBytes"       INTEGER,
  ADD COLUMN "audioDurationSec"     INTEGER,
  ADD COLUMN "audioUploadedAt"      TIMESTAMP(3),
  ADD COLUMN "transcriptRaw"        JSONB,
  ADD COLUMN "speakerMap"           JSONB,
  ADD COLUMN "entities"             JSONB,
  ADD COLUMN "soapDraft"            TEXT,
  ADD COLUMN "critique"             JSONB,
  ADD COLUMN "soapFinal"            TEXT,
  ADD COLUMN "needsReview"          BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN "reviewReason"         TEXT,
  ADD COLUMN "processingStartedAt"  TIMESTAMP(3),
  ADD COLUMN "processingFinishedAt" TIMESTAMP(3),
  ADD COLUMN "processingCostCents"  INTEGER,
  ADD COLUMN "signedSoap"           TEXT;

-- ── 3. Normalise existing string values so the USING cast below
--      succeeds. Anything unrecognised falls back to QUEUED, which is
--      the honest reflection of "we don't know where this row is in
--      the pipeline — start it over if the user uploads audio". ──
UPDATE "transcribe_visits" SET "status" = CASE
  WHEN lower("status") IN ('queued', 'draft')           THEN 'QUEUED'
  WHEN lower("status") IN ('transcribing', 'processing') THEN 'TRANSCRIBING'
  WHEN lower("status") = 'extracting'                    THEN 'EXTRACTING'
  WHEN lower("status") = 'drafting'                      THEN 'DRAFTING'
  WHEN lower("status") = 'critiquing'                    THEN 'CRITIQUING'
  WHEN lower("status") = 'polishing'                     THEN 'POLISHING'
  WHEN lower("status") = 'ready'                         THEN 'READY'
  WHEN lower("status") = 'failed'                        THEN 'FAILED'
  WHEN lower("status") = 'signed'                        THEN 'SIGNED'
  ELSE 'QUEUED'
END;

-- ── 4. Flip the column type from TEXT to the enum. PostgreSQL
--      rebuilds any indexes on the column automatically; the existing
--      transcribe_visits_status_idx survives. ──
ALTER TABLE "transcribe_visits"
  ALTER COLUMN "status" DROP DEFAULT,
  ALTER COLUMN "status" TYPE "TranscribeVisitStatus"
    USING "status"::"TranscribeVisitStatus",
  ALTER COLUMN "status" SET DEFAULT 'QUEUED';
