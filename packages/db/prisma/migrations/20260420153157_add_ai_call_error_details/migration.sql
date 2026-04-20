-- T-M17.1: persist the raw model response on FAILED ai_calls rows so we
-- can diagnose SCHEMA_FAIL / JSON_PARSE_FAIL incidents without relying on
-- the worker log buffer. Observability only — the writer
-- (packages/ai/src/anthropic.ts) caps the value at ~10 KB to keep row
-- size bounded. Contains model-output PHI when set; same privacy envelope
-- as the existing transcribe_visits columns, stays behind practiceId.
ALTER TABLE "ai_calls" ADD COLUMN "errorDetails" TEXT;
