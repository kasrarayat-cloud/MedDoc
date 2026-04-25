-- Phase 1B: ADMIN_API_ACCESS audit-action value.
-- Logged on every successful admin-API hit so the audit trail
-- distinguishes UI page renders (ADMIN_DASHBOARD_ACCESS) from
-- API consumption.

ALTER TYPE "AuditAction" ADD VALUE 'ADMIN_API_ACCESS';
