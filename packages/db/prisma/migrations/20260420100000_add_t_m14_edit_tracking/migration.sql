-- T-M14.1: per-doctor edit tracking.
--   1) pgvector extension (requires pgvector/pgvector:pg16 postgres image)
--   2) transcribe_visits.soapL6Original — immutable L6 snapshot
--   3) doctor_edit_patterns — one row per signed visit with L6 original

-- ------------------------------------------------------------------
-- 1. pgvector extension
-- ------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "vector";

-- ------------------------------------------------------------------
-- 2. transcribe_visits.soapL6Original
-- ------------------------------------------------------------------
ALTER TABLE "transcribe_visits"
  ADD COLUMN "soapL6Original" TEXT;

-- ------------------------------------------------------------------
-- 3. doctor_edit_patterns
-- ------------------------------------------------------------------
CREATE TABLE "doctor_edit_patterns" (
    "id"           TEXT NOT NULL,
    "visitId"      TEXT NOT NULL,
    "doctorId"     TEXT NOT NULL,
    "originalSoap" TEXT NOT NULL,
    "editedSoap"   TEXT NOT NULL,
    "editDistance" INTEGER NOT NULL,
    "embedding"    vector(1536),
    "createdAt"    TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "doctor_edit_patterns_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "doctor_edit_patterns_visitId_key"
  ON "doctor_edit_patterns"("visitId");

CREATE INDEX "doctor_edit_patterns_doctorId_createdAt_idx"
  ON "doctor_edit_patterns"("doctorId", "createdAt");

CREATE INDEX "doctor_edit_patterns_doctorId_editDistance_idx"
  ON "doctor_edit_patterns"("doctorId", "editDistance");

ALTER TABLE "doctor_edit_patterns"
  ADD CONSTRAINT "doctor_edit_patterns_visitId_fkey"
  FOREIGN KEY ("visitId") REFERENCES "transcribe_visits"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "doctor_edit_patterns"
  ADD CONSTRAINT "doctor_edit_patterns_doctorId_fkey"
  FOREIGN KEY ("doctorId") REFERENCES "users"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;
