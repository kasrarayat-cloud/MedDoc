// ============================================================================
// Sentry — Node server init (Marketing) — Round 3 PR-H
// ----------------------------------------------------------------------------
// Marketing has no PHI exposure. Init stays minimal — errors only,
// no PII, no traces.
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
  profilesSampleRate: 0,
  sendDefaultPii: false,
  beforeSend(event) {
    if (!dsn) return null;
    return event;
  },
});
