// ============================================================================
// NextAuth Edge-Safe Shared Config (apps/meddoc-pro)
// ----------------------------------------------------------------------------
// The real config lives in @meddoc/auth so apps/scribe can share it. This
// file re-exports it as the default for back-compat with existing imports
// (src/proxy.ts, src/lib/nextauth.ts).
// ============================================================================

export { authConfig as default } from '@meddoc/auth';
