// ============================================================================
// Next.js register() hook — Sentry runtime dispatch (M7)
// ----------------------------------------------------------------------------
// Next calls register() once per runtime. We load the matching Sentry
// config based on which runtime is active. Sentry docs style.
// ============================================================================

export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    await import('./sentry.server.config');
  }
  if (process.env.NEXT_RUNTIME === 'edge') {
    await import('./sentry.edge.config');
  }
}
