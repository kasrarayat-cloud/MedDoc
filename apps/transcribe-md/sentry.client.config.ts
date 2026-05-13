// ============================================================================
// Sentry — browser init (TranscribeMD) — T-M16.3
// ----------------------------------------------------------------------------
// Client init uses NEXT_PUBLIC_* because webpack bundles this at build
// time. PHI scrubbing via the same redactPhi util as the server side.
// ============================================================================

import * as Sentry from '@sentry/nextjs';
import { redactPhi } from '@meddoc/ai';
import { scrubSentryEvent } from '@/lib/sentry-scrub';

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN_TRANSCRIBE_MD?.trim();

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
    // 2026-05-13 audit P1-B — see server config for rationale.
    scrubSentryEvent(event, redactPhi);
    return event;
  },
});
