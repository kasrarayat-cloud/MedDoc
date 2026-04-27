// ============================================================================
// Admin-API gate (Phase 1B) — wrap every /api/admin/* handler
// ----------------------------------------------------------------------------
// Common contract for the new admin endpoints:
//
//   1. Read the session via auth(). Look up `Product.SUPER_ADMIN` in
//      the user's products[] (falling back to a Prisma read when
//      the JWT doesn't carry products).
//   2. If absent — return a 404 with an empty body. We deliberately
//      don't 401/403, to avoid revealing the route exists. Same
//      posture as /admin/* page rendering (notFound() in layout.tsx).
//   3. If present — write an ADMIN_API_ACCESS audit row tagged with
//      the route name + method, then call the handler.
//
// The handler runs with the verified session and a reference to the
// request, so each endpoint stays minimal:
//
//   export const GET = adminApi('audit-logs:list', async (req, ctx) => {
//     // ctx.session is guaranteed-SUPER_ADMIN here
//     return NextResponse.json({...});
//   });
// ============================================================================

import type { NextRequest } from 'next/server';
import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';
import { Product } from '@prisma/client';

import { auth } from '@/lib/nextauth';
import { logAudit } from '@/lib/audit';
import { isAdminSessionStale } from '@/lib/admin-session-freshness';

/** What admin handlers actually need — slim subset of the next-auth
 *  session. The full app `Session` from @meddoc/auth requires
 *  `fullName` which next-auth's `auth()` doesn't return; admin
 *  handlers don't need it. */
export interface AdminSession {
  user: {
    id: string;
    email: string | null;
    role?: string | null;
    practiceId?: string | null;
  };
}

export interface AdminContext {
  session: AdminSession;
  /** The route key passed to adminApi(); used in audit logs and
   *  error messages. */
  routeKey: string;
}

type AdminHandler = (
  req: NextRequest,
  ctx: AdminContext
) => Promise<NextResponse | Response> | NextResponse | Response;

/** 404 response, identical body across all admin routes so a probing
 *  attacker can't distinguish "wrong-method" from "not-admin" from
 *  "route-doesn't-exist". */
function notFoundResponse(): NextResponse {
  return new NextResponse('Not Found', { status: 404 });
}

export function adminApi(
  routeKey: string,
  handler: AdminHandler
): (req: NextRequest) => Promise<NextResponse | Response> {
  return async (req: NextRequest) => {
    const sessionOrNull = await auth().catch(() => null);
    if (!sessionOrNull?.user?.id) return notFoundResponse();

    // Re-check products from DB so a stale JWT can't grant access
    // after a SUPER_ADMIN revocation. Cheap (indexed PK lookup).
    const userRow = await prisma.user.findUnique({
      where: { id: sessionOrNull.user.id },
      select: { products: true, isActive: true },
    });
    if (!userRow || !userRow.isActive) return notFoundResponse();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const products = (userRow.products as any[] | undefined) ?? [];
    if (!products.includes(Product.SUPER_ADMIN)) return notFoundResponse();

    // Phase 19 — h16-admin-session-7day. Reject admin API calls on
    // sessions older than 12 h even though the cookie stays valid
    // for the consumer-doctor flow. Forces a fresh re-auth on this
    // surface specifically.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const sessionId = (sessionOrNull.user as any).sessionId as string | undefined;
    if (await isAdminSessionStale(sessionId)) return notFoundResponse();

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const u = sessionOrNull.user as any;
    const session: AdminSession = {
      user: {
        id: u.id,
        email: u.email ?? null,
        role: u.role ?? null,
        practiceId: u.practiceId ?? null,
      },
    };

    void logAudit({
      action: 'ADMIN_API_ACCESS',
      targetType: 'AdminAPI',
      targetId: routeKey,
      metadata: {
        routeKey,
        method: req.method,
        path: new URL(req.url).pathname,
      },
    });

    try {
      return await handler(req, { session, routeKey });
    } catch (err) {
      console.error(
        `[admin-api:${routeKey}] handler threw:`,
        err instanceof Error ? err.message : err
      );
      // Generic 500 — don't expose stack traces.
      return NextResponse.json(
        { error: 'Internal server error' },
        { status: 500 }
      );
    }
  };
}
