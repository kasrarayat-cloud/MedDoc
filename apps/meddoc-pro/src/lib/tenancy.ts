// ============================================================================
// Multi-tenancy helpers (apps/meddoc-pro re-export)
// ----------------------------------------------------------------------------
// Implementations moved to @meddoc/auth in M1 so apps/scribe can share the
// same tenant scoping rules. This file keeps the old import path alive for
// all existing callers.
// ============================================================================

// ⚠️ `canBypassTenantScope` IS NOT RE-EXPORTED — it no longer exists.
// Ruled 2026-08-06: no role bypasses the practice wall through the app. This
// app's four consumers read auditLog/user/apiUsage and never a clinical table,
// so nothing here loses a capability it was using on charts; the SUPER_ADMIN
// rows simply stop seeing OTHER practices' audit and usage rows.
export { tenantScope, assertSamePracticeUser, TenantScopeError } from '@meddoc/auth';
