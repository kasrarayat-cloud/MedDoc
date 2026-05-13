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
import {
  RATE_LIMITS,
  clientIpFromRequest,
  rateLimitOr429,
} from '@/lib/rate-limit';
import { redactPhi } from '@meddoc/ai';

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
    // Unauth sink — bot-spam guard via per-IP CLIENT_ERRORS bucket.
    const blocked = rateLimitOr429(
      RATE_LIMITS.CLIENT_ERRORS,
      clientIpFromRequest(req)
    );
    if (blocked) return blocked;

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError('invalid JSON body', 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) return apiError('invalid payload', 400);

    const d = parsed.data;
    // 2026-05-13 audit P1-G — the file's posture was "stack might
    // carry stringified props; message/digest/url shouldn't". The
    // audit findings disagreed: Next.js render errors stringify
    // props on the message too, and URL pathSearch may carry
    // patient names (per P1-C). Redact symmetrically so the log
    // line is PHI-safe regardless of upstream behavior. URL gets
    // its query string stripped entirely — operational triage
    // needs the path, not the query.
    const safeUrl =
      typeof d.url === 'string'
        ? (() => {
            const q = d.url.indexOf('?');
            return q >= 0 ? d.url.slice(0, q) : d.url;
          })()
        : undefined;
    console.error(
      '[client-error]',
      JSON.stringify({
        errorId: d.errorId,
        scope: d.scope,
        message: d.message ? redactPhi(d.message) : undefined,
        digest: d.digest ? redactPhi(d.digest) : undefined,
        url: safeUrl,
        userAgent: d.userAgent,
        // stack on its own line — see below.
      })
    );
    if (d.stack) {
      // T-M16.3: React render stacks shouldn't carry PHI but some libs
      // stringify props into error messages; scrub before logging.
      console.error(
        `[client-error] ${d.errorId} stack:\n${redactPhi(d.stack)}`
      );
    }

    return NextResponse.json({ ok: true }, { status: 202 });
  }
);
