-- S4b — audit actions for the two bulk PHI-egress paths.
--
-- Additive only: two new labels on an existing enum. No table is created,
-- altered or dropped, and no row is written or read. Postgres cannot DROP an
-- enum label, so the rollback for this migration is "leave the labels in
-- place" — unused labels are inert and cost nothing.
--
-- ALTER TYPE ... ADD VALUE is transaction-safe on PG 12+ (prod is 16.13). The
-- new values are not USED in this transaction, which is the one thing PG still
-- forbids.
ALTER TYPE "AuditAction" ADD VALUE 'EXPORT_ACCOUNT_ARCHIVE_DOWNLOADED';
ALTER TYPE "AuditAction" ADD VALUE 'EXPORT_PATIENT_ARCHIVE_DOWNLOADED';
