// ============================================================================
// Admin-API gate (Phase 1B) — wrap every /api/admin/* handler
// ----------------------------------------------------------------------------
// Common contract for the new admin endpoints:
//
//   1. Require the dedicated admin host and read the cookie session via auth().
//   2. Re-check the matching database session, account lifecycle, current
//      SUPER_ADMIN product entitlement, expiry/freshness, force-logout marker,
//      and verified MFA. The ordinary JWT callback may fail open for clinician
//      availability; this gate never does.
//   3. If any check fails — return a 404. We deliberately
//      don't 401/403, to avoid revealing the route exists. Same
//      posture as /admin/* page rendering (notFound() in layout.tsx).
//   4. If present — write an ADMIN_API_ACCESS audit row tagged with
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

import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { auth } from "@/lib/nextauth";
import { logRequiredAdminAudit } from "@/lib/audit";
import { isAdminRequestHost } from "@/lib/admin-host";
import { verifyFreshPlatformAdminSession } from "@/lib/admin-session-freshness";
import { recordTemplateTwinControlAccess } from "@/lib/template-twin/release-control-access-audit";
import { TEMPLATE_TWIN_RELEASE_CONTROL_SERVICE_ROLE } from "@/lib/template-twin/release-control-db";

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
  /** Opaque live-session claim for server-only authorization services.
   * Keep it out of `session.user` so generic response serializers cannot
   * accidentally echo it. */
  verifiedSessionId: string;
  /** The route key passed to adminApi(); used in audit logs and
   *  error messages. */
  routeKey: string;
}

type AdminHandler = (
  req: NextRequest,
  ctx: AdminContext,
) => Promise<NextResponse | Response> | NextResponse | Response;

/** 404 response, identical body across all admin routes so a probing
 *  attacker can't distinguish "wrong-method" from "not-admin" from
 *  "route-doesn't-exist". */
function notFoundResponse(): NextResponse {
  return new NextResponse("Not Found", { status: 404 });
}

export function adminApi(
  routeKey: string,
  handler: AdminHandler,
): (req: NextRequest) => Promise<NextResponse | Response> {
  return async (req: NextRequest) => {
    if (!isAdminRequestHost(req.headers)) return notFoundResponse();

    const sessionOrNull = await auth().catch(() => null);
    if (!sessionOrNull?.user?.id) return notFoundResponse();
    const verified = await verifyFreshPlatformAdminSession({
      claimedUserId: sessionOrNull.user.id,
      sessionId: sessionOrNull.user.sessionId,
    });
    if (!verified) return notFoundResponse();

    const session: AdminSession = {
      user: {
        id: verified.userId,
        email: verified.email,
        role: verified.role,
        practiceId: verified.practiceId,
      },
    };

    try {
      if (
        process.env.QUILLMD_SERVICE_ROLE ===
        TEMPLATE_TWIN_RELEASE_CONTROL_SERVICE_ROLE
      ) {
        await recordTemplateTwinControlAccess({
          actorId: verified.userId,
          actorEmail: verified.email,
          practiceId: verified.practiceId,
          routeKey,
          request: req,
        });
      } else {
        await logRequiredAdminAudit({
          action: "ADMIN_API_ACCESS",
          userId: verified.userId,
          userEmail: verified.email,
          practiceId: verified.practiceId,
          targetType: "AdminAPI",
          targetId: routeKey,
          metadata: {
            routeKey,
            method: req.method,
            path: new URL(req.url).pathname,
            sessionCreatedAt: verified.sessionCreatedAt.toISOString(),
          },
        });
      }
    } catch {
      console.error(
        `[admin-api:${routeKey}] required access audit failed; request denied`,
      );
      return notFoundResponse();
    }

    try {
      return await handler(req, {
        session,
        verifiedSessionId: verified.sessionId,
        routeKey,
      });
    } catch {
      console.error(`[admin-api:${routeKey}] handler failed closed`);
      // Generic 500 — don't expose stack traces.
      return NextResponse.json(
        { error: "Internal server error" },
        { status: 500 },
      );
    }
  };
}
