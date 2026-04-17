// ============================================================================
// Internal service-token auth (cross-app /api/internal/*)
// ----------------------------------------------------------------------------
// Scribe calls apps/meddoc-pro's internal routes with a shared bearer
// token. This helper does the two-layer check per M2 plan D5:
//   1. Constant-time token equality against SCRIBE_SERVICE_TOKEN env
//   2. IP allowlist — only accept requests originating on the Docker
//      bridge network (private-range IPs). Prevents accidental external
//      exposure even if Caddy is misconfigured to route /api/internal/*.
// ============================================================================

import { timingSafeEqual } from 'node:crypto';
import type { NextRequest } from 'next/server';

function isPrivateIp(ip: string | null): boolean {
  if (!ip) return false;
  // Strip IPv6 bracketing + any zone id
  const clean = ip.replace(/^\[|\]$/g, '').split('%')[0];
  if (clean === '127.0.0.1' || clean === '::1') return true;
  // IPv4 RFC 1918 + loopback. Docker bridges usually 172.16.0.0/12 +
  // 172.17.0.0/16 for the default bridge; compose networks land in
  // 172.18-172.31.
  const v4 = clean.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)$/);
  if (v4) {
    const [, a, b] = v4.map(Number);
    if (a === 10) return true;
    if (a === 127) return true;
    if (a === 172 && b >= 16 && b <= 31) return true;
    if (a === 192 && b === 168) return true;
  }
  // IPv6 ULA
  if (/^f[cd][0-9a-f]{2}:/i.test(clean)) return true;
  return false;
}

function extractCallerIp(req: NextRequest): string | null {
  // Docker-internal calls won't have x-forwarded-for (Caddy is the only
  // hop that adds it, and Caddy shouldn't be proxying /api/internal/*).
  // If the header IS present, the request came through an external proxy
  // and must be rejected regardless of whether the token is correct.
  const xff = req.headers.get('x-forwarded-for');
  if (xff) return null; // Signal external hop — reject.
  // `req.ip` is not reliable; peek at x-real-ip set by the container, or
  // fall back to the request's remote address header.
  return (
    req.headers.get('x-real-ip') ||
    req.headers.get('x-client-ip') ||
    null
  );
}

function constantTimeEq(a: string, b: string): boolean {
  const ab = Buffer.from(a, 'utf8');
  const bb = Buffer.from(b, 'utf8');
  if (ab.length !== bb.length) return false;
  return timingSafeEqual(ab, bb);
}

export type InternalAuthResult =
  | { ok: true }
  | { ok: false; status: 401 | 403; error: string };

export function verifyInternalRequest(req: NextRequest): InternalAuthResult {
  const expected = process.env.SCRIBE_SERVICE_TOKEN;
  if (!expected) {
    return { ok: false, status: 403, error: 'Internal API is disabled (SCRIBE_SERVICE_TOKEN unset).' };
  }

  const auth = req.headers.get('authorization') || '';
  const m = auth.match(/^Bearer\s+(.+)$/i);
  if (!m) return { ok: false, status: 401, error: 'Missing bearer token.' };
  const provided = m[1].trim();
  if (!constantTimeEq(provided, expected)) {
    return { ok: false, status: 401, error: 'Invalid token.' };
  }

  const callerIp = extractCallerIp(req);
  if (!isPrivateIp(callerIp)) {
    return {
      ok: false,
      status: 403,
      error: 'Internal API is not reachable externally.',
    };
  }

  return { ok: true };
}
