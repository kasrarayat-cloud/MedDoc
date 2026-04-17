// ============================================================================
// Sentry — Node server init (MedDoc Pro) — M7
// ----------------------------------------------------------------------------
// beforeSend runs on every captured event + transaction. We scrub every
// string-ish field with redactPhi() from @meddoc/ai so raw transcripts,
// SOAP content, and Rx text can't land in Sentry by accident. The
// scrubber is conservative: anything >20 words collapses to a length
// marker; email/phone/SSN patterns get masked.
// ============================================================================

import * as Sentry from '@sentry/nextjs';
import { redactPhi } from '@meddoc/ai';

const dsn = process.env.SENTRY_DSN_MEDDOC_PRO?.trim() || process.env.SENTRY_DSN?.trim();

Sentry.init({
  dsn: dsn || undefined,
  environment: process.env.SENTRY_ENVIRONMENT?.trim() || process.env.NODE_ENV,
  release: process.env.SENTRY_RELEASE?.trim() || undefined,
  // Errors only — performance sampling stays off until we decide on a
  // budget. Low volume is better than flood + noise + unknown PHI paths.
  tracesSampleRate: 0,
  profilesSampleRate: 0,
  sendDefaultPii: false,
  beforeSend(event) {
    // Don't send anything in dev without an explicit DSN — prevents
    // accidental stderr spam when devs start the app locally.
    if (!dsn) return null;
    if (typeof event.message === 'string') {
      event.message = redactPhi(event.message);
    }
    if (event.extra && typeof event.extra === 'object') {
      const extra = event.extra as Record<string, unknown>;
      for (const k of Object.keys(extra)) {
        const v = extra[k];
        if (typeof v === 'string') extra[k] = redactPhi(v);
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
