// ============================================================================
// NextAuth (Auth.js v5) — Full Node Runtime Configuration (apps/transcribe-md)
// ----------------------------------------------------------------------------
// Imports the edge-safe shared config from `./auth.config.ts` and layers on:
//   - A Credentials provider (email + bcrypt password)
//   - A 7-day session.maxAge override (vs. 8 hours on the shared config).
//     The longer TTL is fine for a solo-doctor consumer app; the clinical
//     apps (meddoc-pro, scribe) keep 8 hours for HIPAA reasons.
//   - Silent product-grant: an existing MedDoc Pro user logging in here
//     who doesn't yet have TRANSCRIBE_MD gets it appended to `products`
//     before the sign-in flow returns.
//
// Single-session enforcement + UserSession tracking is already wired up
// by the shared jwt() callback in @meddoc/auth — we inherit it by
// spreading authConfig below.
// ============================================================================

import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { headers as requestHeaders } from "next/headers";
import bcrypt from "bcryptjs";
import * as Sentry from "@sentry/nextjs";

import authConfig from "@/lib/auth.config";
import prisma from "@meddoc/db";
import {
  createSessionValidationJwtCallback,
  computeDeviceFingerprint,
  randomSessionToken,
  revokeSession,
  revokeAllUserSessions,
  type UserRole,
} from "@meddoc/auth";
import { Product, type Prisma } from "@prisma/client";
import { isEmailVerificationRequired } from "@/lib/email-enabled";
import { hasCompleteMfaEnrollment } from "@/lib/mfa-enrollment-state";
import {
  isLoginRequestAllowed,
  isSessionRequestAllowed,
} from "@/lib/auth-surface";
import { logAudit } from "@/lib/audit";
import {
  hasTemplateTwinAdminAppAccess,
  isTemplateTwinAdminAppService,
  transcribeMdSessionPolicyForService,
} from "@/lib/template-twin/admin-app-service";
import {
  CredentialSessionAuthorityError,
  finalizeCredentialSession,
  recordCredentialFailure,
  type CredentialSecondFactorProof,
  type CredentialSessionSurface,
  type CredentialUserSnapshot,
} from "@/lib/credential-session-authority";
import {
  RATE_LIMITS,
  checkSharedRateLimit,
  clientIpFromHeaders,
} from "@/lib/rate-limit";
import { readSignedSessionAuthority } from "@/lib/signed-session-authority";

/** 7 days. Longer than meddoc-pro (8hr) because TranscribeMD is a solo
 *  consumer surface, not a PHI-heavy clinical tool. */
const SESSION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60;

/** T-M18.3 A18: pre-computed dummy bcrypt hash used to equalize the
 *  wall-clock time of paths that would otherwise short-circuit before
 *  running the real `bcrypt.compare` below. The specific plaintext
 *  doesn't matter — bcrypt.compare against this hash returns false for
 *  every realistic input. Computed once at module load (~100 ms). */
const DUMMY_PASSWORD_HASH = bcrypt.hashSync(
  "timing-equalizer-never-matches",
  12,
);

async function runDummyPasswordCheck(password: string): Promise<void> {
  await bcrypt.compare(password, DUMMY_PASSWORD_HASH).catch(() => false);
}

function credentialSnapshot(
  user: CredentialUserSnapshot,
): CredentialUserSnapshot {
  return {
    id: user.id,
    email: user.email,
    name: user.name,
    practiceId: user.practiceId,
    passwordHash: user.passwordHash,
    role: user.role,
    products: [...user.products],
    emailVerified: user.emailVerified,
    mfaEnabled: user.mfaEnabled,
    mfaSecret: user.mfaSecret,
    mfaVerifiedAt: user.mfaVerifiedAt,
    mfaBackupCodes: [...user.mfaBackupCodes],
  };
}

async function registerCredentialFailure(
  snapshot: CredentialUserSnapshot,
  surface: CredentialSessionSurface,
) {
  try {
    return await prisma.$transaction((tx: Prisma.TransactionClient) =>
      recordCredentialFailure(tx, { snapshot, surface }),
    );
  } catch {
    console.error("[auth] credential failure authority could not be recorded");
    return null;
  }
}

const nextAuth = NextAuth({
  ...authConfig,

  session: {
    strategy: "jwt",
    maxAge: SESSION_MAX_AGE_SECONDS,
    // Refresh the JWT on activity — when the user is active within this
    // window, their cookie is re-signed with a bumped expiry. 1 day picked
    // so active users don't suddenly get logged out on day 7.
    updateAge: 24 * 60 * 60,
  },

  // Raw auth() is the authorization entry point for many server components
  // and route handlers. Apply the physician product/role policy in the JWT
  // callback itself so those paths receive the same current database fence as
  // getSession(), including revocation after demotion or product removal.
  callbacks: {
    ...authConfig.callbacks,
    jwt: createSessionValidationJwtCallback(
      transcribeMdSessionPolicyForService(),
      { acceptPrevalidatedSession: true },
    ),
  },

  providers: [
    Credentials({
      name: "Email + Password",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
        // MFA — set when the user has mfaEnabled=true. Either a 6-digit
        // TOTP token OR a one-time recovery code is required (validated
        // below after the password check). loginAction handles the
        // two-step UX; authorize re-validates here as defense in depth
        // — even a direct signIn() call from somewhere else has to
        // include the second factor or it fails.
        totpToken: { label: "TOTP", type: "text" },
        recoveryCode: { label: "Recovery", type: "text" },
      },
      async authorize(credentials, request) {
        if (!request?.headers || !isLoginRequestAllowed(request.headers)) {
          return null;
        }
        const rateLimit = await checkSharedRateLimit(
          RATE_LIMITS.LOGIN,
          clientIpFromHeaders(request.headers),
        );
        if (!rateLimit.allowed) return null;

        const email =
          typeof credentials?.email === "string"
            ? credentials.email.trim().toLowerCase()
            : "";
        const password =
          typeof credentials?.password === "string" ? credentials.password : "";
        if (!email || !password) {
          await runDummyPasswordCheck(password);
          return null;
        }
        const totpToken =
          typeof credentials?.totpToken === "string"
            ? credentials.totpToken
            : "";
        const recoveryCode =
          typeof credentials?.recoveryCode === "string"
            ? credentials.recoveryCode
            : "";
        const sessionSurface: CredentialSessionSurface =
          isTemplateTwinAdminAppService() ? "admin" : "physician";

        let user;
        try {
          user = await prisma.user.findUnique({ where: { email } });
        } catch {
          await runDummyPasswordCheck(password);
          // Database-driver errors can embed connection URLs and credentials.
          console.error("[auth] user lookup failed; login denied");
          return null;
        }
        if (!user) {
          await runDummyPasswordCheck(password);
          return null;
        }
        if (!user.isActive) {
          await runDummyPasswordCheck(password);
          return null;
        }
        // Phase 6Z (PHASE-6Z-08): reject suspended/soft-deleted users at the
        // login form rather than letting them complete authorize() and then
        // having validateSession reject their first authenticated request.
        // The fields exist on the User row already (no extra select needed —
        // findUnique above selects everything by default).
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        if ((user as any).suspendedAt) {
          await runDummyPasswordCheck(password);
          void logAudit({
            action: "LOGIN_FAILED",
            userId: user.id,
            userEmail: user.email,
            practiceId: user.practiceId,
            success: false,
            errorCode: "ACCOUNT_SUSPENDED",
          });
          return null;
        }
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        if ((user as any).softDeletedAt) {
          await runDummyPasswordCheck(password);
          void logAudit({
            action: "LOGIN_FAILED",
            userId: user.id,
            userEmail: user.email,
            practiceId: user.practiceId,
            success: false,
            errorCode: "ACCOUNT_SOFT_DELETED",
          });
          return null;
        }
        if (user.lockedUntil && user.lockedUntil > new Date()) {
          await runDummyPasswordCheck(password);
          return null;
        }

        // T-M16.2 defense-in-depth: the email-verification policy is
        // primarily enforced in loginAction (which can return a
        // dedicated "needsVerificationFor" state to surface the resend
        // affordance to the user). If someone bypasses the action and
        // hits NextAuth signIn directly, we still block here. No
        // counter increment — this isn't a failed credential, it's a
        // state gate. This policy is deliberately separate from provider
        // delivery health, so losing Resend configuration cannot weaken auth.
        //
        // T-M18.3 A18: run a no-op bcrypt.compare before early-return
        // so this path takes the same wall-clock time as the verified
        // path (which hits the real bcrypt below). Prevents an attacker
        // from distinguishing "email exists + unverified" via response
        // timing.
        if (isEmailVerificationRequired() && user.emailVerified === null) {
          await runDummyPasswordCheck(password);
          return null;
        }

        const valid = await bcrypt.compare(password, user.passwordHash);
        if (!valid) {
          // The direct Auth.js endpoint does not traverse loginAction's rate
          // limiter. Serialize thresholding on the current user row so
          // parallel password attempts cannot step past the lock boundary.
          const failure = await registerCredentialFailure(
            credentialSnapshot(user),
            sessionSurface,
          );
          void logAudit({
            action: "LOGIN_FAILED",
            userId: user.id,
            userEmail: user.email,
            practiceId: user.practiceId,
            success: false,
            errorCode: failure?.locked
              ? "ACCOUNT_LOCKED_NOW"
              : "CREDENTIALS_MISMATCH",
            metadata: {
              failedLoginCount: failure?.failedLoginCount ?? null,
            },
          });
          return null;
        }

        // F9-1: Entitlement gate. Pre-fix this branch silently granted
        // TRANSCRIBE_MD to any MEDDOC_PRO user who logged in here, which
        // was an entitlement bypass — any valid account could promote
        // itself. Now we require the product to already be on the user
        // before issuing a session. Granting must go through an admin
        // surface or billing webhook (not auto on first login).
        //
        // Phase 1A: SUPER_ADMIN bypasses the entitlement check —
        // platform admins need access to the scribe surface to
        // debug incidents for customer tickets. Symmetric with the
        // meddoc-pro side.
        const tmHasTranscribe = user.products.includes(Product.TRANSCRIBE_MD);
        const tmHasSuperAdmin = user.products.includes(Product.SUPER_ADMIN);
        if (!tmHasTranscribe && !tmHasSuperAdmin) {
          void logAudit({
            action: "LOGIN_FAILED",
            userId: user.id,
            userEmail: user.email,
            practiceId: user.practiceId,
            success: false,
            errorCode: "NO_TRANSCRIBE_MD_ENTITLEMENT",
          });
          return null;
        }

        // admin.quillmd.com has a separately routed process and host-only
        // cookie. Reject ordinary physicians before UserSession rotation;
        // route-level gates still re-check the narrower current authority.
        if (
          isTemplateTwinAdminAppService() &&
          !hasTemplateTwinAdminAppAccess({
            role: user.role,
            products: user.products,
          })
        ) {
          void logAudit({
            action: "LOGIN_FAILED",
            userId: user.id,
            userEmail: user.email,
            practiceId: user.practiceId,
            success: false,
            errorCode: "NO_ADMIN_SURFACE_AUTHORITY",
          });
          return null;
        }

        // Verify the expensive second-factor proof against the request-start
        // snapshot, but do not consume recovery state yet. The transaction
        // below re-locks and compares this exact credential/MFA snapshot,
        // consumes a recovery code, resets lockout state, rotates sessions,
        // and creates the new UserSession as one linearized operation.
        let secondFactor: CredentialSecondFactorProof = { kind: "none" };
        let mfaFailureCode: string | null = null;
        if (user.mfaEnabled) {
          if (!hasCompleteMfaEnrollment(user)) {
            void logAudit({
              action: "MFA_CHALLENGE_FAILED",
              userId: user.id,
              userEmail: user.email,
              practiceId: user.practiceId,
              success: false,
              errorCode: "MFA_ENROLLMENT_INCOMPLETE",
              metadata: { stage: "login" },
            });
            return null;
          }
          // Lazy-import the MFA verifier so the edge bundle never pulls
          // it in (mfa.ts uses node:crypto + otplib).
          const { verifyStoredMfaTotpToken, findMatchingRecoveryHash } =
            await import("@/lib/mfa");

          if (totpToken) {
            if (
              verifyStoredMfaTotpToken(user.id, user.mfaSecret, totpToken)
            ) {
              secondFactor = { kind: "totp" };
            } else {
              mfaFailureCode = "INVALID_TOTP";
            }
          } else if (recoveryCode) {
            const matched = findMatchingRecoveryHash(
              recoveryCode,
              user.mfaBackupCodes,
            );
            if (matched) {
              secondFactor = { kind: "recovery", matchedHash: matched };
            } else {
              mfaFailureCode = "INVALID_RECOVERY_CODE";
            }
          } else {
            mfaFailureCode = "TOTP_REQUIRED";
          }

          if (mfaFailureCode) {
            const failure = await registerCredentialFailure(
              credentialSnapshot(user),
              sessionSurface,
            );
            void logAudit({
              action: "MFA_CHALLENGE_FAILED",
              userId: user.id,
              userEmail: user.email,
              practiceId: user.practiceId,
              success: false,
              errorCode: mfaFailureCode,
              metadata: {
                stage: "login",
                failedLoginCount: failure?.failedLoginCount ?? null,
                locked: failure?.locked ?? null,
              },
            });
            return null;
          }
        }

        const ipAddress =
          request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
          request.headers.get("x-real-ip") ??
          null;
        const userAgent = request.headers.get("user-agent");
        const acceptLanguage = request.headers.get("accept-language");
        const prevalidatedSessionId = randomSessionToken();

        try {
          await prisma.$transaction((tx: Prisma.TransactionClient) =>
            finalizeCredentialSession(tx, {
              snapshot: credentialSnapshot(user),
              surface: sessionSurface,
              secondFactor,
              requireVerifiedEmail: isEmailVerificationRequired(),
              sessionToken: prevalidatedSessionId,
              ipAddress,
              userAgent,
              deviceFingerprint: computeDeviceFingerprint(
                userAgent,
                acceptLanguage,
              ),
            }),
          );
        } catch (error) {
          if (!(error instanceof CredentialSessionAuthorityError)) {
            console.error(
              "[auth] credential session finalization failed; login denied",
            );
          }
          return null;
        }

        return {
          id: user.id,
          email: user.email,
          name: user.name,
          role: user.role as UserRole,
          practiceId: user.practiceId,
          prevalidatedSessionId,
        };
      },
    }),
  ],

  events: {
    async signIn({ user }) {
      if (!user?.id) return;
      // The immutable LOGIN_SUCCESS receipt was required inside the same
      // transaction as UserSession issuance. This event only establishes
      // non-PHI observability context after Auth.js accepts that transaction.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const practiceId = (user as any).practiceId as string | undefined;
      Sentry.setUser({ id: user.id });
      if (practiceId) Sentry.setTag("practiceId", practiceId);
    },
    async signOut(message) {
      // next-auth v5's signOut event fires with a discriminated union.
      // Pull userId when it's available; tolerate the other shapes.
      const token = "token" in message ? message.token : null;
      const userId =
        token && typeof token === "object" && "sub" in token
          ? ((token as { sub?: string }).sub ?? null)
          : null;
      // Revoke the server-side UserSession row on sign-out. Without this only
      // the cookie is cleared and the row survives — so a JWT that lingers
      // in-flight (e.g. the post-sign-out /login redirect load racing the
      // cookie-clear) re-validates the session and re-mints the cookie,
      // intermittently leaving the user signed in. Revoke by the token's
      // sessionId claim, with a userId fallback. Fires for EVERY sign-out path
      // (TopNav signOut(), the menu, the API route).
      const sessionId =
        token && typeof token === "object" && "sessionId" in token
          ? ((token as { sessionId?: string }).sessionId ?? null)
          : null;
      try {
        if (sessionId) await revokeSession(sessionId);
        else if (userId) await revokeAllUserSessions(userId);
      } catch {
        console.error("[auth:signOut] session revoke failed");
      }
      if (userId) {
        void logAudit({ action: "LOGOUT", userId });
      }
      // Round 3 PR-H — clear Sentry user scope on signout so a
      // subsequent error from this process doesn't carry the
      // departed user's id.
      Sentry.setUser(null);
    },
  },
});

function deniedAuthHandlerResponse(): Response {
  return new Response("Not Found", {
    status: 404,
    headers: {
      "Cache-Control": "no-store, no-cache, must-revalidate",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function sessionRevocationUnavailableResponse(): Response {
  return new Response("Secure sign-out is temporarily unavailable.", {
    status: 503,
    headers: {
      "Cache-Control": "no-store, no-cache, must-revalidate",
      "Retry-After": "5",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

async function handleAuthorizedAuthPost(
  request: Parameters<typeof nextAuth.handlers.POST>[0],
): Promise<Response> {
  if (new URL(request.url).pathname !== "/api/auth/signout") {
    return nextAuth.handlers.POST(request);
  }

  // Auth.js clears its cookie even when the signOut event throws. Establish
  // durable revocation independently from the DB-backed auth() callback and
  // refuse to hand the request to Auth.js until that row is gone.
  const authority = await readSignedSessionAuthority(request.headers);
  if (authority.cookiePresent) {
    if (!authority.sessionId) return sessionRevocationUnavailableResponse();
    try {
      await revokeSession(authority.sessionId);
    } catch {
      console.error("[auth:signOut] durable pre-revocation failed");
      return sessionRevocationUnavailableResponse();
    }
  }
  return nextAuth.handlers.POST(request);
}

/**
 * Bind every Auth.js HTTP endpoint to the same exact process/origin pair as
 * raw server-side session reads. This runs before Auth.js parses a cookie or
 * invokes the database-backed JWT callback.
 */
export const handlers = {
  GET: (request: Parameters<typeof nextAuth.handlers.GET>[0]) =>
    isSessionRequestAllowed(request.headers)
      ? nextAuth.handlers.GET(request)
      : Promise.resolve(deniedAuthHandlerResponse()),
  POST: (request: Parameters<typeof nextAuth.handlers.POST>[0]) =>
    isSessionRequestAllowed(request.headers)
      ? handleAuthorizedAuthPost(request)
      : Promise.resolve(deniedAuthHandlerResponse()),
};

/**
 * Central Node request-context fence for every raw auth() call. Missing
 * request context, an unknown process identity, or a host/process mismatch
 * returns no session without asking Auth.js to resolve the cookie.
 */
export async function auth() {
  try {
    if (!isSessionRequestAllowed(await requestHeaders())) return null;
  } catch {
    return null;
  }
  return nextAuth.auth();
}

export const { signIn, signOut } = nextAuth;
