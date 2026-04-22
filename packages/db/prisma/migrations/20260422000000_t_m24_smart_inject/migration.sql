-- T-M24.smart (rolled-back-in-place)
--
-- Originally added `injectedMinioKey` on transcribe_templates as part
-- of the in-progress T-M24.smart work on a feature branch. That branch
-- (PR #48) was closed without merging when the custom-templates
-- feature was dropped from the launch scope — but the migration had
-- already been applied on the dev VPS, so _prisma_migrations carries
-- a row for this name.
--
-- This stub exists ONLY so `prisma migrate status` sees a matching
-- folder for that applied row. The next migration
-- (20260422100000_drop_t_m24_templates) DROPs the entire table, which
-- removes the column as a side effect. The IF NOT EXISTS guard keeps
-- this a no-op on fresh databases that never had the column.

ALTER TABLE "transcribe_templates"
    ADD COLUMN IF NOT EXISTS "injectedMinioKey" TEXT;
