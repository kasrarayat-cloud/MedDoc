// ============================================================================
// Sentry — browser init (Marketing) — Round 3 PR-H
// ----------------------------------------------------------------------------
// Marketing has no PHI (the marketing app is the public site — no
// patients, no transcripts, no SOAP). The redactPhi() pass we run on
// the transcribe-md side is unnecessary here. Init stays narrow:
// errors only, no traces, no replays.
//
// DSN read from NEXT_PUBLIC_SENTRY_DSN_MARKETING so the marketing app
// lands on its own Sentry project (separate alert rules from
// transcribe-md). Empty DSN → init is a no-op.
// ============================================================================

import * as Sentry from '@sentry/nextjs';

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN_MARKETING?.trim();

Sentry.init({
  dsn: dsn || undefined,
  environment:
    process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT?.trim() || 'production',
  release: process.env.NEXT_PUBLIC_SENTRY_RELEASE?.trim() || undefined,
  tracesSampleRate: 0,
  replaysSessionSampleRate: 0,
  replaysOnErrorSampleRate: 0,
  sendDefaultPii: false,
  beforeSend(event) {
    if (!dsn) return null;
    return event;
  },
});
