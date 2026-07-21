// T-M2: single-session tracking helpers. Node-only; don't import these
// from edge middleware — the shared authConfig below uses dynamic
// import() so the edge bundle never pulls them in.
export {
  recordSessionLogin,
  validateSession,
  revokeSession,
  revokeAllUserSessionsFromCurrentSession,
  revokeAllUserSessions,
  getUserSessions,
  randomSessionToken,
  computeDeviceFingerprint,
} from "./user-session";
export type {
  RecordSessionLoginInput,
  RevokeAllUserSessionsFromCurrentSessionInput,
  SessionValidationGrant,
  SessionValidationPolicy,
  ValidateSessionInput,
} from "./user-session";

// ============================================================================
// @meddoc/auth — shared auth surface for apps/meddoc-pro and apps/scribe
// ----------------------------------------------------------------------------
// Minimal lift per M1 plan §D5(a): types + edge-safe NextAuth config +
// tenant helpers. The full NextAuth instance (Credentials provider, signIn
// events that write audit rows) stays inside apps/meddoc-pro because it's
// tightly coupled to that app's audit + session-log modules. apps/scribe
// reuses this config to read the same JWT sessions without a sign-in flow.
// ============================================================================

import type { NextAuthConfig } from "next-auth";
import type { SessionValidationPolicy } from "./user-session";
// Bring the jwt submodule into this compilation unit so the
// `declare module 'next-auth/jwt'` augmentation at the bottom of this file
// can resolve it. Without this, tsc (NodeNext/bundler resolution) reports
// TS2664 on the augmentation in downstream apps.
import type {} from "next-auth/jwt";
import prisma from "@meddoc/db";
import { isExactSyntheticQaRuntimeProfile } from "./synthetic-qa-runtime-profile";

export { isExactSyntheticQaRuntimeProfile } from "./synthetic-qa-runtime-profile";
export {
  hasConfiguredQuillmdRuntimeIdentity,
  isUnconfiguredNextProductionBuild,
  requiresExactQuillmdRuntimeIdentity,
} from "./runtime-identity";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type UserRole = "DOCTOR" | "ADMIN" | "STAFF" | "SUPER_ADMIN";

export interface Session {
  user: {
    id: string;
    email: string;
    /** Display name (mapped from NextAuth's `name` field) */
    fullName: string;
    role: UserRole;
    /** Multi-tenancy: the practice this user belongs to. Used to scope
     *  every query/action to a single tenant. */
    practiceId: string;
  };
}

export class AuthError extends Error {
  code: "UNAUTHENTICATED" | "FORBIDDEN";

  constructor(code: "UNAUTHENTICATED" | "FORBIDDEN", message: string) {
    super(message);
    this.name = "AuthError";
    this.code = code;
  }
}

// ---------------------------------------------------------------------------
// Shared edge-safe NextAuth config
// ----------------------------------------------------------------------------
// Imported by BOTH apps' middleware/proxy (edge runtime — no Node APIs
// allowed here) AND by each app's own `nextauth.ts` which spreads this
// config and adds its node-only providers/events on top.
//
// Rules (same as before M1):
//   ✗ no @meddoc/db / Prisma
//   ✗ no bcryptjs
//   ✗ no next/headers
//
// AUTH_COOKIE_DOMAIN remains a local/non-production compatibility option.
// QuillMD production sessions are deliberately host-only so the physician
// and platform-admin origins never inherit one another's session cookie.
// ---------------------------------------------------------------------------

const cookieDomain = process.env.AUTH_COOKIE_DOMAIN?.trim();
export const QUILLMD_AUTH_SESSION_VERIFIER_PROFILE_ENV =
  "QUILLMD_AUTH_SESSION_VERIFIER_PROFILE" as const;
export const QUILLMD_TEMPLATE_TWIN_ADMIN_CONTROL_SESSION_VERIFIER_PROFILE =
  "template-twin-admin-control-v1" as const;

function usesDedicatedTemplateTwinSessionVerifier(): boolean {
  return (
    process.env.NODE_ENV === "production" &&
    process.env.QUILLMD_SERVICE_ROLE === "template-twin-admin-control" &&
    process.env.QUILLMD_DATABASE_PRINCIPAL_PROFILE === "exact-production-v1" &&
    process.env[QUILLMD_AUTH_SESSION_VERIFIER_PROFILE_ENV] ===
      QUILLMD_TEMPLATE_TWIN_ADMIN_CONTROL_SESSION_VERIFIER_PROFILE
  );
}

type SessionJwtCallback = NonNullable<
  NonNullable<NextAuthConfig["callbacks"]>["jwt"]
>;

/**
 * Build the Node-side JWT callback with the consuming application's current
 * role/product policy. The shared config uses the base lifecycle/tenant
 * policy; physician TranscribeMD supplies DOCTOR + TRANSCRIBE_MD below its
 * Node-only NextAuth configuration.
 */
export function createSessionValidationJwtCallback(
  policy: SessionValidationPolicy = {},
  options: { acceptPrevalidatedSession?: boolean } = {},
): SessionJwtCallback {
  return async ({ token, user }) => {
    if (user) {
      token.id = user.id;
      token.role = user.role;
      token.practiceId = user.practiceId;

      const prevalidatedSessionId =
        options.acceptPrevalidatedSession &&
        typeof user.prevalidatedSessionId === "string" &&
        user.prevalidatedSessionId.length >= 16
          ? user.prevalidatedSessionId
          : null;
      if (prevalidatedSessionId) {
        token.sessionId = prevalidatedSessionId;
      } else {
        try {
          const [headersMod, sessionMod] = await Promise.all([
            import("next/headers"),
            import("./user-session"),
          ]);
          const h = await headersMod.headers();
          const ipAddress =
            h.get("x-forwarded-for")?.split(",")[0]?.trim() ??
            h.get("x-real-ip") ??
            null;
          const userAgent = h.get("user-agent") ?? null;
          const acceptLanguage = h.get("accept-language") ?? null;
          const sessionToken = sessionMod.randomSessionToken();
          await sessionMod.recordSessionLogin({
            userId: user.id,
            sessionToken,
            ipAddress,
            userAgent,
            deviceFingerprint: sessionMod.computeDeviceFingerprint(
              userAgent,
              acceptLanguage,
            ),
          });
          token.sessionId = sessionToken;
        } catch {
          console.error("[auth] UserSession record failed; sign-in denied.");
          return null;
        }
      }
    }

    const sessionId = token.sessionId;
    const claimedUserId =
      typeof token.id === "string" && token.id.length > 0
        ? token.id
        : typeof token.sub === "string" && token.sub.length > 0
          ? token.sub
          : null;
    const claimedPracticeId =
      typeof token.practiceId === "string" && token.practiceId.length > 0
        ? token.practiceId
        : null;
    if (!sessionId || !claimedUserId || !claimedPracticeId) return null;

    // The isolated Template Twin control process deliberately has no raw
    // user_sessions privilege. Its route gate immediately re-verifies these
    // exact user/session claims through a narrow SECURITY DEFINER function.
    if (usesDedicatedTemplateTwinSessionVerifier()) return token;

    try {
      const { validateSession } = await import("./user-session");
      const current = await validateSession({
        sessionToken: sessionId,
        expectedUserId: claimedUserId,
        expectedPracticeId: claimedPracticeId,
        allowedRoles: policy.allowedRoles,
        requiredProducts: policy.requiredProducts,
        ...(policy.anyOf !== undefined ? { anyOf: policy.anyOf } : {}),
      });
      if (!current) return null;

      // Current database identity is authoritative. Email/name may change
      // without revoking a session; role and tenant claims are refreshed only
      // after the exact role policy and tenant binding above remain valid.
      token.id = current.user.id;
      token.sub = current.user.id;
      token.email = current.user.email;
      token.name = current.user.name;
      token.role = current.user.role;
      token.practiceId = current.user.practiceId;
      token.sessionId = sessionId;
      return token;
    } catch {
      // Session validation is authorization evidence. A database or validator
      // error cannot preserve a previously trusted JWT in any environment.
      console.error("[auth] UserSession validation failed; session denied.");
      return null;
    }
  };
}

// app.quillmd.com and admin.quillmd.com intentionally use separate host-only
// sessions. A parent-domain cookie collapses that origin boundary and
// contradicts the platform-admin Caddy allowlist. Fail during production
// server initialization instead of accepting a warning-only configuration.
if (
  process.env.NODE_ENV === "production" &&
  process.env.NEXT_PHASE !== "phase-production-build" &&
  cookieDomain
) {
  throw new Error(
    "AUTH_COOKIE_DOMAIN must be unset in production; QuillMD sessions are host-only.",
  );
}

export const authConfig: NextAuthConfig = {
  providers: [],

  pages: {
    signIn: "/login",
  },

  session: {
    strategy: "jwt",
    maxAge: 60 * 60 * 8, // 8 hours — short for HIPAA
  },

  // T-M16.3: hard-fail in production if AUTH_SECRET is unset. The dev
  // fallback below stays for local development (NODE_ENV !== production)
  // so `npm run dev` without an env file still works. In prod a missing
  // value would silently sign every JWT with the hardcoded literal —
  // identical across deployments — which is a forgeable-session class
  // bug. Fail fast + loud instead.
  //
  // NEXT_PHASE guard: `next build` sets NODE_ENV=production but doesn't
  // need a real secret (no actual auth happens during prerender / page-
  // data collection, and the build-time env typically lacks .env). Skip
  // the throw during the build phase — we only want to fail at
  // container-start time, not at build time.
  secret:
    process.env.NODE_ENV === "production" &&
    process.env.NEXT_PHASE !== "phase-production-build" &&
    !process.env.AUTH_SECRET
      ? (() => {
          throw new Error(
            "AUTH_SECRET is required in production. Set it in /opt/meddoc-pro/.env (openssl rand -base64 32) and recreate the app containers.",
          );
        })()
      : process.env.AUTH_SECRET ||
        "dev_secret_change_in_production_min_32_chars_xyz",

  trustHost: true,

  // This explicit switch controls every Auth.js auxiliary cookie (callback,
  // CSRF, PKCE, state, nonce, and WebAuthn challenge), not just the session
  // override below. The production startup gate separately requires HTTPS.
  useSecureCookies: process.env.NODE_ENV === "production",

  // Security audit P1-H (2026-05-13): always emit the cookie
  // hardening flags. Previously this whole block was gated on
  // `cookieDomain` being set; with AUTH_COOKIE_DOMAIN unset (the
  // default), the app silently inherited NextAuth defaults. Auth.js
  // v5 ships sensible defaults in production, but the only thing
  // pinning httpOnly/sameSite/secure for THIS app was that
  // assumption. Emitting the block unconditionally pins the posture
  // explicitly. The `domain` option is the only field that varies
  // by env — it's added only when AUTH_COOKIE_DOMAIN is set so the
  // app retains host-only behaviour by default.
  cookies: {
    sessionToken: {
      name:
        process.env.NODE_ENV === "production"
          ? "__Secure-authjs.session-token"
          : "authjs.session-token",
      options: {
        httpOnly: true,
        sameSite: "lax" as const,
        path: "/",
        secure: process.env.NODE_ENV === "production",
        ...(cookieDomain ? { domain: cookieDomain } : {}),
      },
    },
  },

  callbacks: {
    /**
     * Runs on EVERY request that matches the middleware matcher.
     * Returning `true` allows the request through; returning `false`
     * triggers an automatic redirect to `pages.signIn`.
     */
    authorized({ auth, request: { nextUrl } }) {
      if (
        process.env.AUTH_USE_MOCK === "true" &&
        (process.env.NODE_ENV !== "production" ||
          isExactSyntheticQaRuntimeProfile(process.env))
      ) {
        return true;
      }

      const isLoggedIn = !!auth?.user;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const role = (auth?.user as any)?.role as string | undefined;
      const path = nextUrl.pathname;
      const isOnDashboard = path.startsWith("/dashboard");
      const isOnAdmin = path.startsWith("/system-admin");
      const isOnVisits = path.startsWith("/visits");

      // Require login for protected areas (meddoc-pro + scribe both).
      if ((isOnDashboard || isOnAdmin || isOnVisits) && !isLoggedIn)
        return false;

      if (isLoggedIn && role) {
        const isAdminRole = role === "ADMIN" || role === "SUPER_ADMIN";
        if (isOnAdmin && !isAdminRole) {
          return new Response(null, {
            status: 302,
            headers: {
              Location: new URL("/dashboard", nextUrl).toString(),
              "Cache-Control": "no-store, no-cache, must-revalidate",
            },
          });
        }
      }

      return true;
    },

    jwt: createSessionValidationJwtCallback(),

    async session({ session, token }) {
      if (session.user && token) {
        session.user.id = token.id as string;
        session.user.email = token.email ?? "";
        session.user.name = token.name ?? null;
        session.user.role = token.role;
        session.user.practiceId = token.practiceId;
        session.user.sessionId = token.sessionId;
      }
      return session;
    },

    async redirect({ url, baseUrl }) {
      if (url.startsWith(baseUrl)) return url;
      if (url.startsWith("/")) return `${baseUrl}${url}`;
      return baseUrl;
    },
  },
};

// ---------------------------------------------------------------------------
// Tenant helpers
// ----------------------------------------------------------------------------
// Role semantics:
//   DOCTOR, STAFF  — scoped to their own practice, and within that, only
//                    patients they created/are assigned to.
//   ADMIN          — scoped to their own practice, but sees EVERY patient
//                    and user within it.
//   SUPER_ADMIN    — bypass all tenant scoping. Platform ops only.
// ---------------------------------------------------------------------------

export function canBypassTenantScope(session: Session): boolean {
  return session.user.role === "SUPER_ADMIN";
}

export function tenantScope(session: Session): { practiceId?: string } {
  if (canBypassTenantScope(session)) return {};
  return { practiceId: session.user.practiceId };
}

export class TenantScopeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TenantScopeError";
  }
}

export async function assertSamePracticeUser(
  session: Session,
  targetUserId: string,
): Promise<void> {
  if (canBypassTenantScope(session)) return;
  const target = await prisma.user.findUnique({
    where: { id: targetUserId },
    select: { practiceId: true },
  });
  if (!target) {
    throw new TenantScopeError("User not found.");
  }
  if (target.practiceId !== session.user.practiceId) {
    throw new TenantScopeError("User not found.");
  }
}

// ---------------------------------------------------------------------------
// NextAuth module augmentation
// ----------------------------------------------------------------------------
// Adds our custom fields (id, role, practiceId) to the NextAuth Session,
// User, and JWT types. Declared here (not in each app) so both apps and
// this package see the same shape as soon as they import from @meddoc/auth.
// Before M1 this lived at apps/meddoc-pro/src/types/next-auth.d.ts; that
// file is removed now — this block is the single source of truth.
// ---------------------------------------------------------------------------

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      role: UserRole;
      practiceId: string;
      /** Opaque token matching an exact current row in user_sessions.
       * Runtime authentication rejects sessions when this is absent. */
      sessionId?: string;
    } & import("next-auth").DefaultSession["user"];
  }

  interface User {
    id: string;
    email: string;
    name?: string | null;
    role: UserRole;
    practiceId: string;
    /** Server-only handoff from a credential transaction that atomically
     * created the exact UserSession before Auth.js JWT issuance. */
    prevalidatedSessionId?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id: string;
    role: UserRole;
    practiceId: string;
    /** T-M2: see Session.user.sessionId above. */
    sessionId?: string;
  }
}

// ---------------------------------------------------------------------------
// patientAccessWhere
// ---------------------------------------------------------------------------

/**
 * Returns a Prisma `where` predicate that scopes Patient queries to what
 * the given session can see. Exported so other data modules (appointments,
 * clinical notes, Scribe visits) can use it as a nested relation filter:
 *   prisma.appointment.findMany({
 *     where: { patient: patientAccessWhere(session) }
 *   })
 * — which pushes tenant isolation down to the Postgres join.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function patientAccessWhere(session: Session): any {
  const base: Record<string, unknown> = { deletedAt: null };

  if (session.user.role === "SUPER_ADMIN") {
    return base;
  }

  base.practiceId = session.user.practiceId;

  if (session.user.role === "ADMIN") {
    return base;
  }

  // DOCTOR / STAFF — additionally constrained to their own patients.
  return {
    ...base,
    OR: [
      { createdById: session.user.id },
      { assignedDoctorId: session.user.id },
    ],
  };
}
