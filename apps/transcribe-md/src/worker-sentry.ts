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
import { scrubSentryEvent } from '@/lib/sentry-scrub';

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
    // 2026-05-13 audit P1-B — extended scrub. See sentry-scrub.ts.
    scrubSentryEvent(event, redactPhi);
    return event;
  },
});

/** Capture a pipeline error with visitId + layer tags, BEFORE the
 *  caller re-throws to BullMQ (so retry semantics are preserved). No-op
 *  when Sentry DSN is unset — keeps dev quiet.
 *
 *  Round 3 PR-H — A11-P1 user/practice context.
 *  PHI guard: only IDs (UUIDs) are passed through. Never log patient
 *  name, MRN, DOB, email, or transcript content. The redactPhi
 *  beforeSend hook is a backstop; primary defense is never sending
 *  PHI in the first place. The {userId, practiceId} tags let ops
 *  filter "all errors for this practice" without re-reading audit. */
export function captureWorkerException(
  err: unknown,
  ctx: {
    visitId: string;
    layer: string;
    userId?: string | null;
    practiceId?: string | null;
  }
): void {
  Sentry.captureException(err, {
    tags: {
      visitId: ctx.visitId,
      layer: ctx.layer,
      ...(ctx.userId ? { userId: ctx.userId } : {}),
      ...(ctx.practiceId ? { practiceId: ctx.practiceId } : {}),
    },
    user: ctx.userId ? { id: ctx.userId } : undefined,
  });
}
