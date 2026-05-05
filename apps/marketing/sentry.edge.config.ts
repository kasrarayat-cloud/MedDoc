// ============================================================================
// Sentry — edge runtime init (Marketing) — Round 3 PR-H
// ----------------------------------------------------------------------------
// Marketing has no PHI. Init stays minimal.
// ============================================================================

import * as Sentry from '@sentry/nextjs';

const dsn =
  process.env.SENTRY_DSN_MARKETING?.trim() ||
  process.env.SENTRY_DSN?.trim();

Sentry.init({
  dsn: dsn || undefined,
  environment:
    process.env.SENTRY_ENVIRONMENT?.trim() || process.env.NODE_ENV,
  release: process.env.SENTRY_RELEASE?.trim() || undefined,
  tracesSampleRate: 0,
  sendDefaultPii: false,
  beforeSend(event) {
    if (!dsn) return null;
    return event;
  },
});
