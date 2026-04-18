// ============================================================================
// NextAuth Edge-Safe Shared Config (apps/transcribe-md)
// ----------------------------------------------------------------------------
// Re-exports the shared config from @meddoc/auth so the proxy/middleware can
// use it at the edge. The full Node-side NextAuth instance is in
// ./nextauth.ts, which adds Credentials + overrides session.maxAge.
// ============================================================================

export { authConfig as default } from '@meddoc/auth';
