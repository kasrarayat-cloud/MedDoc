-- T-M24: custom SOAP templates (POC)
--
-- Adds `transcribe_templates` — one row per doctor-uploaded .docx with
-- {{placeholder}} tokens — plus the optional `templateId` FK and
-- `filledTemplate` (JSON-serialised token→content from L7f) columns
-- on `transcribe_visits`.
--
-- Both of the new visit columns are nullable so every existing visit
-- is untouched (NULL templateId = "Standard output only", same flow
-- as pre-T-M24). ON DELETE SET NULL on the FK so soft-deleting a
-- template doesn't cascade-clobber historical visits that referenced
-- it; the DB row stays NULL'd and the filled-docx endpoint returns
-- 404 ("template no longer available").
--
-- The MinIO object at `templates/{userId}/{templateId}.docx` in the
-- existing `transcribe-md-audio` bucket is managed by the application
-- layer; the DB only stores the key.

CREATE TABLE "transcribe_templates" (
    "id"               TEXT        NOT NULL,
    "userId"           TEXT        NOT NULL,
    "name"             TEXT        NOT NULL,
    "originalFileName" TEXT        NOT NULL,
    "minioKey"         TEXT        NOT NULL,
    "extractedText"    TEXT        NOT NULL,
    "tokens"           TEXT[]      NOT NULL,
    "createdAt"        TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt"        TIMESTAMP(3) NOT NULL,
    "deletedAt"        TIMESTAMPTZ(6),

    CONSTRAINT "transcribe_templates_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "transcribe_templates_minioKey_key"
    ON "transcribe_templates"("minioKey");

CREATE INDEX "transcribe_templates_userId_deletedAt_idx"
    ON "transcribe_templates"("userId", "deletedAt");

ALTER TABLE "transcribe_templates"
    ADD CONSTRAINT "transcribe_templates_userId_fkey"
    FOREIGN KEY ("userId") REFERENCES "users"("id")
    ON DELETE CASCADE ON UPDATE CASCADE;

-- ── transcribe_visits extensions ──
ALTER TABLE "transcribe_visits" ADD COLUMN "templateId"     TEXT;
ALTER TABLE "transcribe_visits" ADD COLUMN "filledTemplate" TEXT;

CREATE INDEX "transcribe_visits_templateId_idx"
    ON "transcribe_visits"("templateId");

ALTER TABLE "transcribe_visits"
    ADD CONSTRAINT "transcribe_visits_templateId_fkey"
    FOREIGN KEY ("templateId") REFERENCES "transcribe_templates"("id")
    ON DELETE SET NULL ON UPDATE CASCADE;
