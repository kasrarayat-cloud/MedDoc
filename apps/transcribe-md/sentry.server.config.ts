// ============================================================================
// Sentry — Node server init (TranscribeMD) — T-M16.3
// ----------------------------------------------------------------------------
// Mirrors apps/meddoc-pro/sentry.server.config.ts (same beforeSend
// PHI-scrub pattern via redactPhi from @meddoc/ai) but reads
// SENTRY_DSN_TRANSCRIBE_MD instead so the two apps can land on
// separate Sentry projects / alert channels.
//
// beforeSend runs on every captured event + transaction. We scrub
// every string-ish field with redactPhi() so raw transcripts, SOAP
// content, and Rx text can't land in Sentry by accident.
// ============================================================================

import * as Sentry from '@sentry/nextjs';
import { redactPhi } from '@meddoc/ai';
import { scrubSentryEvent } from '@/lib/sentry-scrub';

const dsn =
  process.env.SENTRY_DSN_TRANSCRIBE_MD?.trim() ||
  process.env.SENTRY_DSN?.trim();

Sentry.init({
  dsn: dsn || undefined,
  environment:
    process.env.SENTRY_ENVIRONMENT?.trim() || process.env.NODE_ENV,
  release: process.env.SENTRY_RELEASE?.trim() || undefined,
  // Errors only — performance sampling stays off until we decide on a
  // budget. Low volume is better than flood + noise + unknown PHI
  // paths.
  tracesSampleRate: 0,
  profilesSampleRate: 0,
  sendDefaultPii: false,
  beforeSend(event) {
    // Don't send anything without an explicit DSN — prevents stderr
    // spam when devs start the app locally without Sentry configured.
    if (!dsn) return null;
    // 2026-05-13 audit P1-B: extend the scrub to event.request.data /
    // .url / .query_string / .headers / .cookies and event.user.
    // See sentry-scrub.ts for the field inventory.
    scrubSentryEvent(event, redactPhi);
    return event;
  },
});
