-- T-M24.smart — auto-injected template binary
--
-- When a doctor uploads a template with zero {{tokens}}, the upload
-- endpoint runs detectSections + injectTokens to produce a secondary
-- .docx with {{token}} placeholders substituted into the clinical
-- sections (while letterhead / tables / signature / disclaimer stay
-- verbatim). The injected binary gets its own MinIO object; the
-- original stays so the doctor can always download / re-inject.
--
-- Nullable because:
--   1. Backfill: existing rows (pre-smart-injection) stay valid.
--   2. Runtime: injection is a best-effort step; an upload with no
--      detected clinical sections (or a detector error) persists the
--      original only, and the L7f worker / download route fall back
--      to minioKey. Non-null = smart-mode; null = token-fill mode.

ALTER TABLE "transcribe_templates"
  ADD COLUMN "injectedMinioKey" TEXT;
