// ============================================================================
// Next.js register() hook — Sentry runtime dispatch (M7, Scribe)
// ----------------------------------------------------------------------------
// Worker + ws containers call `import './sentry.server.config'` directly
// at their own entrypoints (outside the Next.js lifecycle). Next calls
// this register() for the web container.
// ============================================================================

export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    await import('./sentry.server.config');
  }
  if (process.env.NEXT_RUNTIME === 'edge') {
    await import('./sentry.edge.config');
  }
}
