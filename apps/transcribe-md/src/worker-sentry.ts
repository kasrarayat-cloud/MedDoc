// ============================================================================
// Worker-side Sentry init (T-M16.3)
// ----------------------------------------------------------------------------
// The BullMQ worker is a plain Node process, NOT Next.js. @sentry/nextjs
// doesn't wire itself here, so we init @sentry/node directly. Shares
// the same DSN + redactPhi posture as apps/transcribe-md/sentry.server.config.ts
// so events land on the same project as the web app.
// ============================================================================

import * as Sentry from '@sentry/node';
import { redactPhi } from '@meddoc/ai';

const dsn =
  process.env.SENTRY_DSN_TRANSCRIBE_MD?.trim() ||
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

/** Capture a pipeline error with visitId + layer tags, BEFORE the
 *  caller re-throws to BullMQ (so retry semantics are preserved). No-op
 *  when Sentry DSN is unset — keeps dev quiet. */
export function captureWorkerException(
  err: unknown,
  ctx: { visitId: string; layer: string }
): void {
  Sentry.captureException(err, {
    tags: {
      visitId: ctx.visitId,
      layer: ctx.layer,
    },
  });
}
