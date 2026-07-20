// ============================================================================
// apps/transcribe-md — getSession() wrapper
// ----------------------------------------------------------------------------
// Calls auth() to read the shared JWT cookie (validated by the shared
// jwt() callback, which enforces single-session via UserSession lookups).
// Re-reads the DB to refresh isActive/role/practiceId so emergency
// revocation takes effect on the next request. Same shape and semantics
// as apps/scribe/src/lib/auth.ts.
// ============================================================================

import { auth } from "@/lib/nextauth";
import { headers } from "next/headers";
import prisma from "@meddoc/db";
import {
  AuthError,
  validateSession,
  type Session,
  type UserRole,
} from "@meddoc/auth";
import {
  evaluateTemplateTwinRollout,
  pinTemplateTwinRollout,
  TemplateTwinRolloutError,
  type TemplateTwinRolloutToken,
} from "@/lib/template-twin/rollout";
import { isPhysicianRequestHost } from "@/lib/admin-host";
import { isTranscribeMdPhysicianAppService } from "@/lib/template-twin/admin-app-service";

export { AuthError };
export type { Session, UserRole };

async function assertPhysicianRequestContext(): Promise<void> {
  if (!isTranscribeMdPhysicianAppService()) {
    throw new AuthError(
      "FORBIDDEN",
      "Clinical access is unavailable on the administrative service.",
    );
  }
  try {
    if (isPhysicianRequestHost(await headers())) return;
  } catch (error) {
    if (error instanceof AuthError) throw error;
  }
  throw new AuthError(
    "FORBIDDEN",
    "Clinical access is unavailable on this host.",
  );
}

export async function getSession(): Promise<Session | null> {
  try {
    await assertPhysicianRequestContext();
    const nextAuthSession = await auth();
    const userId = nextAuthSession?.user?.id;
    const sessionId = nextAuthSession?.user?.sessionId;
    const claimedPracticeId = nextAuthSession?.user?.practiceId;
    if (!userId || !sessionId || !claimedPracticeId) return null;

    const current = await validateSession({
      sessionToken: sessionId,
      expectedUserId: userId,
      expectedPracticeId: claimedPracticeId,
      allowedRoles: ["DOCTOR"],
      requiredProducts: ["TRANSCRIBE_MD"],
    });
    if (!current) return null;

    return {
      user: {
        id: current.user.id,
        email: current.user.email,
        fullName: current.user.name ?? "Unknown",
        role: current.user.role as UserRole,
        practiceId: current.user.practiceId,
      },
    };
  } catch {
    return null;
  }
}

export async function requireSession(): Promise<Session> {
  const s = await getSession();
  if (!s) throw new AuthError("UNAUTHENTICATED", "You must be logged in.");
  return s;
}

/** Fresh, fail-closed role evidence for physician-only clinical surfaces. */
export async function requireFreshDoctorIdentity(userId: string): Promise<{
  role: "DOCTOR";
  practiceId: string;
  email: string;
  fullName: string;
  rolloutToken: TemplateTwinRolloutToken;
}> {
  try {
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: {
        id: true,
        email: true,
        name: true,
        role: true,
        isActive: true,
        practiceId: true,
        deactivatedAt: true,
        suspendedAt: true,
        softDeletedAt: true,
        products: true,
        practice: {
          select: { id: true, isActive: true, templateTwinEnabled: true },
        },
      },
    });
    if (
      !user ||
      user.id !== userId ||
      !user.isActive ||
      user.role !== "DOCTOR" ||
      !user.practiceId ||
      user.practice.id !== user.practiceId ||
      !user.practice.isActive ||
      user.deactivatedAt !== null ||
      user.suspendedAt !== null ||
      user.softDeletedAt !== null ||
      !user.products.includes("TRANSCRIBE_MD")
    ) {
      throw new AuthError(
        "FORBIDDEN",
        "An active physician account is required for Template Twin.",
      );
    }
    const rollout = evaluateTemplateTwinRollout({
      practiceEnabled: user.practice.templateTwinEnabled,
    });
    if (!rollout.allowed) {
      throw new AuthError("FORBIDDEN", rollout.reason);
    }
    let rolloutToken: TemplateTwinRolloutToken;
    try {
      rolloutToken = await pinTemplateTwinRollout({
        practiceId: user.practiceId,
      });
    } catch (error) {
      if (error instanceof TemplateTwinRolloutError) {
        throw new AuthError("FORBIDDEN", error.message);
      }
      throw error;
    }
    return {
      role: "DOCTOR",
      practiceId: user.practiceId,
      email: user.email,
      fullName: user.name ?? "Unknown",
      rolloutToken,
    };
  } catch (error) {
    if (error instanceof AuthError) throw error;
    // Role evidence is mandatory on this boundary. Do not fall back to a
    // potentially stale JWT when the database cannot confirm the role.
    throw new AuthError(
      "FORBIDDEN",
      "An active physician account is required for Template Twin.",
    );
  }
}

export type TemplateTwinDoctorSession = Session & {
  /**
   * The persisted global + practice generations admitted by the fresh
   * physician authorization check. Configuration mutations must carry this
   * exact token to their final transaction; they must never re-pin after
   * provider, rendering, or browser work has started.
   */
  templateTwinRolloutToken: TemplateTwinRolloutToken;
};

export async function requireDoctorSession(): Promise<TemplateTwinDoctorSession> {
  await assertPhysicianRequestContext();
  const nextAuthSession = await auth();
  if (
    !nextAuthSession?.user?.id ||
    !nextAuthSession.user.sessionId ||
    !nextAuthSession.user.practiceId
  ) {
    throw new AuthError("UNAUTHENTICATED", "You must be logged in.");
  }
  const doctor = await requireFreshDoctorIdentity(nextAuthSession.user.id);
  if (doctor.practiceId !== nextAuthSession.user.practiceId) {
    throw new AuthError(
      "FORBIDDEN",
      "Your session tenant is no longer current. Sign in again.",
    );
  }
  return {
    templateTwinRolloutToken: doctor.rolloutToken,
    user: {
      id: nextAuthSession.user.id,
      email: doctor.email,
      fullName: doctor.fullName,
      role: doctor.role,
      practiceId: doctor.practiceId,
    },
  };
}

/** Read the current NextAuth session cookie and return its required
 * UserSession binding. Missing bindings are unauthenticated. */
export async function getCurrentSessionId(): Promise<string | null> {
  const session = await auth();
  return session?.user?.sessionId ?? null;
}
