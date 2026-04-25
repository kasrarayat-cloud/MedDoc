-- Phase 1A: audit coverage + SUPER_ADMIN role.
--
-- Adds new AuditAction values for transcribe-md's mutation surface
-- (closing H2 from the ultra-final audit) plus ADMIN_DASHBOARD_ACCESS
-- for the new /admin route. Also extends the Product enum with
-- SUPER_ADMIN for the admin-dashboard gate.
--
-- Enum ADD VALUE is non-transactional in Postgres; each ALTER TYPE
-- commits independently. A failure mid-list leaves the enum in a
-- partial state — re-running this migration is idempotent because
-- prisma migrate deploy checks which migrations have applied, and
-- the ALTER TYPE ADD VALUE IF NOT EXISTS wrapper would be needed
-- for a true re-run. For now the partial-state case requires ops
-- to resume the migration manually; unlikely in practice.

-- AlterEnum — AuditAction
ALTER TYPE "AuditAction" ADD VALUE 'ADMIN_DASHBOARD_ACCESS';
ALTER TYPE "AuditAction" ADD VALUE 'VISIT_SIGNED';
ALTER TYPE "AuditAction" ADD VALUE 'VISIT_DELETED';
ALTER TYPE "AuditAction" ADD VALUE 'VISIT_ARCHIVED';
ALTER TYPE "AuditAction" ADD VALUE 'VISIT_UNARCHIVED';
ALTER TYPE "AuditAction" ADD VALUE 'VISIT_RESTORED';
ALTER TYPE "AuditAction" ADD VALUE 'VISIT_RETRY';
ALTER TYPE "AuditAction" ADD VALUE 'VISIT_RETRY_BUDGET_EXHAUSTED';
ALTER TYPE "AuditAction" ADD VALUE 'EXPORT_EMAIL_SENT';
ALTER TYPE "AuditAction" ADD VALUE 'EXPORT_EMAIL_BLOCKED_DESTINATION';
ALTER TYPE "AuditAction" ADD VALUE 'EXPORT_PDF_DOWNLOADED';
ALTER TYPE "AuditAction" ADD VALUE 'EXPORT_DOCX_DOWNLOADED';
ALTER TYPE "AuditAction" ADD VALUE 'EXPORT_CLIPBOARD_COPIED';
ALTER TYPE "AuditAction" ADD VALUE 'TM_PATIENT_CREATED';
ALTER TYPE "AuditAction" ADD VALUE 'TM_PATIENT_UPDATED';
ALTER TYPE "AuditAction" ADD VALUE 'TM_PATIENT_DELETED';
ALTER TYPE "AuditAction" ADD VALUE 'EMAIL_CHANGE_REQUESTED';
ALTER TYPE "AuditAction" ADD VALUE 'EMAIL_CHANGE_CONFIRMED';
ALTER TYPE "AuditAction" ADD VALUE 'ACCOUNT_DELETED';
ALTER TYPE "AuditAction" ADD VALUE 'RX_OVERRIDE_RECORDED';
ALTER TYPE "AuditAction" ADD VALUE 'RX_SIGN_BLOCKED_NO_OVERRIDE';

-- AlterEnum — Product
ALTER TYPE "Product" ADD VALUE 'SUPER_ADMIN';
