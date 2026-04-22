-- Drop all T-M24 state. The custom-templates feature was removed
-- from the launch scope; no production data was ever exposed beyond
-- the development VPS. Reverses:
--   - 20260421211200_t_m24_custom_templates (transcribe_templates +
--     transcribe_visits.templateId/filledTemplate)
--   - 20260422000000_t_m24_smart_inject    (injectedMinioKey column,
--     folded into this drop)
--
-- FK from transcribe_visits → transcribe_templates is dropped
-- explicitly so the column drop below doesn't require CASCADE.

ALTER TABLE "transcribe_visits"
    DROP CONSTRAINT IF EXISTS "transcribe_visits_templateId_fkey";

DROP INDEX IF EXISTS "transcribe_visits_templateId_idx";

ALTER TABLE "transcribe_visits"
    DROP COLUMN IF EXISTS "templateId",
    DROP COLUMN IF EXISTS "filledTemplate";

DROP TABLE IF EXISTS "transcribe_templates";
