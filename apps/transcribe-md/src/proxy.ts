// ============================================================================
// Next.js Edge Middleware — TranscribeMD route protection
// ----------------------------------------------------------------------------
// Runs on the Edge for every request matching `config.matcher`. Uses the
// edge-safe auth.config (no Prisma / Node deps) to check the session
// cookie. On `authorized` returning false, NextAuth redirects to /login
// with a callbackUrl query param.
//
// Prisma-backed session validation (single-session enforcement) happens
// later in the jwt() callback, which only runs in Node — the edge tier
// is for cheap cookie gating.
// ============================================================================

import NextAuth, { type NextAuthRequest } from "next-auth";
import type { NextFetchEvent, NextRequest } from "next/server";
import { NextResponse } from "next/server";
import authConfig from "@/lib/auth.config";
import {
  isTemplateTwinAdminControlPathAllowed,
  isTemplateTwinAdminControlService,
  isTemplateTwinAdminAppPathAllowed,
  isTemplateTwinAdminAppService,
  isTranscribeMdPhysicianProxyPath,
} from "@/lib/template-twin/admin-app-service";

const { auth } = NextAuth(authConfig);
const authenticatedProxy = auth(
  (request: NextAuthRequest, event: NextFetchEvent) => {
    void request;
    void event;
    return NextResponse.next();
  },
);

export default function proxy(request: NextRequest, event: NextFetchEvent) {
  const pathname = request.nextUrl.pathname;
  const adminApp = isTemplateTwinAdminAppService();
  const adminControl = isTemplateTwinAdminControlService();
  if (adminApp || adminControl) {
    const allowed = adminApp
      ? isTemplateTwinAdminAppPathAllowed(pathname)
      : isTemplateTwinAdminControlPathAllowed(pathname);
    if (!allowed) {
      return new NextResponse("Not Found", {
        status: 404,
        headers: {
          "Cache-Control": "no-store, no-cache, must-revalidate",
          "X-Content-Type-Options": "nosniff",
        },
      });
    }
    return authenticatedProxy(request, event);
  }

  // The matcher is intentionally broad so the same immutable image can close
  // the admin process before routing. Preserve the physician process's prior
  // auth-proxy census instead of decoding cookies on every public request.
  return isTranscribeMdPhysicianProxyPath(pathname)
    ? authenticatedProxy(request, event)
    : NextResponse.next();
}

export const config = {
  matcher: ["/:path*"],
};
