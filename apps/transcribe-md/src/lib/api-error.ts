// ============================================================================
// Shared API-route error helpers (T-M11)
// ----------------------------------------------------------------------------
// Every /api/visits/** route runs its body inside withApiHandler() so an
// unexpected throw (Prisma timeout, Node fetch error, whatever) turns
// into a logged 500 with a uniform JSON body — not Next's default
// error page, not a leaked stack trace.
//
// Three exports:
//
//   apiError(message, status)          — canonical error response
//   withApiHandler(prefix, handler)    — wraps a POST/GET handler with
//                                        a top-level try/catch
//   ApiRouteContext<P>                 — the shape Next 16 passes as
//                                        the second arg to a dynamic
//                                        route handler
//
// Intentional design choices
//   • Ownership failures continue to return 404 (not 403). Preventing
//     ID enumeration beats the slightly-more-accurate status code —
//     we comment-document this at every call site so the intent is
//     obvious to future us.
//   • The 500 catch returns JSON even for routes whose happy-path
//     body is binary (pdf/docx/dictation-audio). Callers distinguish
//     by status code; the JSON body is just for log readability.
//   • We don't add an error-code string field (the plan mentioned
//     it as optional). Nothing reads codes today and a wider shape
//     is dead weight until a caller actually branches on it.
// ============================================================================

import { NextResponse, type NextRequest } from 'next/server';

import { SessionUnverifiableError } from '@meddoc/auth';
import { redactPhi } from '@meddoc/ai';

export interface ApiErrorBody {
  error: string;
  /** T-M16.4: machine-readable error taxonomy. Clients that care
   *  branch on this; older clients still read `error` and work
   *  unchanged. SHOUT_CASE so a `switch` feels at home. */
  code?: string;
  /** T-M16.4: hint for clients that have a "retry" affordance —
   *  true when the failure was transient (network blip, upstream
   *  5xx), false when it was a permanent misconfiguration (bad MIME,
   *  oversized file). Absent = caller didn't classify. */
  retry?: boolean;
}

export interface ApiErrorExtras {
  code?: string;
  retry?: boolean;
}

/** Canonical error response. Every route handler uses this (directly
 *  or via withApiHandler) so clients see the same shape for every
 *  failure mode: `{ error: string }`. Optional 3rd arg carries the
 *  T-M16.4 `{code, retry}` classification; omit for routes that don't
 *  care to classify yet. */
export function apiError(
  message: string,
  status: number,
  extras: ApiErrorExtras = {}
): NextResponse<ApiErrorBody> {
  const body: ApiErrorBody = { error: message };
  if (extras.code !== undefined) body.code = extras.code;
  if (extras.retry !== undefined) body.retry = extras.retry;
  return NextResponse.json(body, { status });
}

export interface ApiRouteContext<P extends Record<string, string>> {
  params: Promise<P>;
}

/** Wraps a route handler with a top-level try/catch. An unexpected
 *  throw becomes a logged 500 with a uniform JSON body. Use for
 *  every route handler so the log-prefix + shape stays consistent.
 *
 *  Naming convention for `prefix`:  `api:visits:<last-segment>` —
 *  grepable and disambiguates the sign route from the client-side
 *  "[sign]" log prefixes the worker / client use. */
export function withApiHandler<P extends Record<string, string>>(
  prefix: string,
  handler: (
    req: NextRequest,
    ctx: ApiRouteContext<P>
  ) => Promise<NextResponse>
): (req: NextRequest, ctx: ApiRouteContext<P>) => Promise<NextResponse> {
  return async (req, ctx) => {
    // Performance Auditor Phase 4 (PERFORMANCE_FINDING_002 closure):
    // capture wall-clock for every API route + emit as the
    // `X-Response-Time` header. Phase 4 of the Performance Auditor
    // reads route TTFB from this signal; without it, Phase 4 emits
    // NO_DATA. Server-Timing header makes it visible to dev tools too.
    const t0 = Date.now();
    try {
      const response = await handler(req, ctx);
      const ms = Date.now() - t0;
      response.headers.set('X-Response-Time', `${ms}ms`);
      response.headers.set('Server-Timing', `app;dur=${ms}`);
      return response;
    } catch (err) {
      // ⚠️ #182(1) / #186(a) — "CANNOT TELL" ANSWERS 503, NOT 500.
      //
      // `SessionUnverifiableError` declared `readonly status = 503` and three
      // comments said the request was "REFUSED (503)". NOTHING MAPPED IT TO A
      // RESPONSE. The throw fell through to the catch-all below and the caller
      // received a generic 500 — so the prose asserted a status the system did
      // not send, and a client could not distinguish "retry in a moment" from
      // "this request is broken". Found by an adversarial lens re-reading the
      // author's own comments against the code.
      //
      // 503 is the honest code: the service could not verify the session right
      // now. `Retry-After` is set because that is the whole content of the
      // answer — the session is NOT ended and the next attempt may well work.
      if (err instanceof SessionUnverifiableError) {
        const ms = Date.now() - t0;
        console.error(`[${prefix}] SESSION_UNVERIFIABLE after ${ms}ms — answering 503`);
        const response = apiError(
          'session could not be verified — you have not been signed out; please retry',
          503,
        );
        response.headers.set('Retry-After', '2');
        response.headers.set('X-Response-Time', `${ms}ms`);
        response.headers.set('Server-Timing', `app;dur=${ms}`);
        return response;
      }

      // T-M18.1 A1: scrub before stdout. `err` here is whatever slipped
      // past the handler's own try/catch — Prisma errors in particular
      // quote failing column values in their `.message`, which for
      // routes that write soapFinal / patientName / etc. means PHI
      // landing in Docker logs unscrubbed. redactPhi catches emails,
      // phone, SSN, and falls back to a length marker on long
      // free-text blocks. Every route-level try/catch in this codebase
      // already pipes err through redactPhi; without this line, the
      // catchall defeated the pattern.
      const ms = Date.now() - t0;
      console.error(
        `[${prefix}] unexpected error after ${ms}ms:`,
        redactPhi(err instanceof Error ? err.message : err)
      );
      const response = apiError('internal server error', 500);
      response.headers.set('X-Response-Time', `${ms}ms`);
      response.headers.set('Server-Timing', `app;dur=${ms}`);
      return response;
    }
  };
}
