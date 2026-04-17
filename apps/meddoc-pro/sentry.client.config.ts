// ============================================================================
// Sentry — browser init (MedDoc Pro) — M7
// ----------------------------------------------------------------------------
// Client init must use NEXT_PUBLIC_* because Webpack bundles it. PHI
// scrubbing still runs via the same redactPhi util — if a browser
// error ever carries transcript text in its message (e.g. a failed
// JSON.parse of SOAP content), the scrubber collapses it.
// ============================================================================

import * as Sentry from '@sentry/nextjs';
import { redactPhi } from '@meddoc/ai';

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN_MEDDOC_PRO?.trim();

Sentry.init({
  dsn: dsn || undefined,
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT?.trim() || 'production',
  release: process.env.NEXT_PUBLIC_SENTRY_RELEASE?.trim() || undefined,
  tracesSampleRate: 0,
  replaysSessionSampleRate: 0,
  replaysOnErrorSampleRate: 0,
  sendDefaultPii: false,
  beforeSend(event) {
    if (!dsn) return null;
    if (typeof event.message === 'string') {
      event.message = redactPhi(event.message);
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
