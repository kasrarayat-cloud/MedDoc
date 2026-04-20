// ============================================================================
// Next.js register() hook — Sentry runtime dispatch (T-M16.3)
// ----------------------------------------------------------------------------
// Next calls register() once per runtime. We load the matching Sentry
// config based on which runtime is active. Mirrors apps/meddoc-pro.
// ============================================================================

export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    await import('./sentry.server.config');
  }
  if (process.env.NEXT_RUNTIME === 'edge') {
    await import('./sentry.edge.config');
  }
}
