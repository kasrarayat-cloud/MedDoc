// ============================================================================
// POST /api/client-errors (T-M11)
// ----------------------------------------------------------------------------
// Sink for React error-boundary reports. The client fires this from
// ErrorFallback via sendBeacon so even on a crashed page-unload the
// ops team still sees a log line with:
//   errorId / scope / message / stack / digest / url / userAgent.
//
// Intentionally light:
//   - No auth required. The data is self-reported from the user's
//     browser, we're not trusting it for anything — just correlating
//     a support conversation with server logs.
//   - No persistence. Logs are the durable record. Adding a table
//     invites "clean up old rows" ops work for very little payoff.
//   - Size-capped per field so an attacker can't use this as an
//     unbounded log-injection vector.
//   - PHI-light on design: error.message / error.stack shouldn't
//     contain PHI because error-boundary errors are React render
//     failures, not visit data. If we ever see PHI in these logs
//     that's a separate bug to fix at the source.
// ============================================================================

import { z } from 'zod';
import { NextResponse } from 'next/server';

import { apiError, withApiHandler } from '@/lib/api-error';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const BodySchema = z.object({
  errorId: z.string().min(1).max(100),
  scope: z.string().min(1).max(60),
  message: z.string().max(1_000).optional(),
  stack: z.string().max(10_000).optional(),
  digest: z.string().max(200).optional(),
  url: z.string().max(2_000).optional(),
  userAgent: z.string().max(500).optional(),
});

export const POST = withApiHandler(
  'api:client-errors',
  async (req) => {
    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError('invalid JSON body', 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) return apiError('invalid payload', 400);

    const d = parsed.data;
    console.error(
      '[client-error]',
      JSON.stringify({
        errorId: d.errorId,
        scope: d.scope,
        message: d.message,
        digest: d.digest,
        url: d.url,
        userAgent: d.userAgent,
        // stack on its own line to keep the single-line JSON grep-
        // friendly. Multi-line stack traces break one-line log
        // aggregators; drop them to a separate error() call so
        // correlation still works via errorId.
      })
    );
    if (d.stack) {
      console.error(`[client-error] ${d.errorId} stack:\n${d.stack}`);
    }

    return NextResponse.json({ ok: true }, { status: 202 });
  }
);
