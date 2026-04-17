// ============================================================================
// Multi-tenancy helpers (apps/meddoc-pro re-export)
// ----------------------------------------------------------------------------
// Implementations moved to @meddoc/auth in M1 so apps/scribe can share the
// same tenant scoping rules. This file keeps the old import path alive for
// all existing callers.
// ============================================================================

export {
  canBypassTenantScope,
  tenantScope,
  assertSamePracticeUser,
  TenantScopeError,
} from '@meddoc/auth';
