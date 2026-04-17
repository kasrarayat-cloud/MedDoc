// ============================================================================
// Sentry — Node server init (Scribe) — M7
// ----------------------------------------------------------------------------
// Shared by the Next.js web container, the scribe-worker BullMQ process,
// and the scribe-ws sidecar — each sources this file so every runtime
// has the same PHI scrubber wired via beforeSend.
// ============================================================================

import * as Sentry from '@sentry/nextjs';
import { redactPhi } from '@meddoc/ai';

const dsn = process.env.SENTRY_DSN_SCRIBE?.trim() || process.env.SENTRY_DSN?.trim();

Sentry.init({
  dsn: dsn || undefined,
  environment: process.env.SENTRY_ENVIRONMENT?.trim() || process.env.NODE_ENV,
  release: process.env.SENTRY_RELEASE?.trim() || undefined,
  tracesSampleRate: 0,
  profilesSampleRate: 0,
  sendDefaultPii: false,
  beforeSend(event) {
    if (!dsn) return null;
    if (typeof event.message === 'string') {
      event.message = redactPhi(event.message);
    }
    if (event.extra && typeof event.extra === 'object') {
      for (const k of Object.keys(event.extra)) {
        const v = (event.extra as Record<string, unknown>)[k];
        if (typeof v === 'string') (event.extra as Record<string, unknown>)[k] = redactPhi(v);
      }
    }
    if (Array.isArray(event.breadcrumbs)) {
      for (const crumb of event.breadcrumbs) {
        if (typeof crumb.message === 'string') {
          crumb.message = redactPhi(crumb.message);
        }
      }
    }
    return event;
  },
});
