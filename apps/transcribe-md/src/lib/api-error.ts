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

export interface ApiErrorBody {
  error: string;
}

/** Canonical error response. Every route handler uses this (directly
 *  or via withApiHandler) so clients see the same shape for every
 *  failure mode: `{ error: string }`. */
export function apiError(
  message: string,
  status: number
): NextResponse<ApiErrorBody> {
  return NextResponse.json({ error: message }, { status });
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
    try {
      return await handler(req, ctx);
    } catch (err) {
      console.error(`[${prefix}] unexpected error:`, err);
      return apiError('internal server error', 500);
    }
  };
}
