import prisma from "@meddoc/db";
import { validateSession } from "@meddoc/auth";
import { headers } from "next/headers";

import { AuthError } from "@/lib/auth";
import { isAdminRequestHost } from "@/lib/admin-host";
import { isAdminSessionStale } from "@/lib/admin-session-freshness";
import { hasCompleteMfaEnrollment } from "@/lib/mfa-enrollment-state";
import { auth } from "@/lib/nextauth";

import {
  evaluateTemplateTwinRollout,
  pinTemplateTwinRollout,
  TemplateTwinRolloutError,
} from "./rollout";
import type { TemplateTwinStaticAssetActor } from "./static-assets";
import { isTemplateTwinAdminAppService } from "./admin-app-service";

/** Fresh, fail-closed practice-admin authorization for reusable image review. */
export async function requireTemplateTwinStaticAssetAdmin(): Promise<TemplateTwinStaticAssetActor> {
  if (!isTemplateTwinAdminAppService()) {
    throw new AuthError(
      "FORBIDDEN",
      "Reusable template images are available only from the administrative application.",
    );
  }
  const requestHeaders = await headers().catch(() => null);
  if (!requestHeaders || !isAdminRequestHost(requestHeaders)) {
    throw new AuthError(
      "FORBIDDEN",
      "Reusable template images are available only from the administrative application.",
    );
  }
  const session = await auth().catch(() => null);
  if (!session?.user?.id) {
    throw new AuthError("UNAUTHENTICATED", "You must be logged in.");
  }
  const sessionId = (session.user as { sessionId?: string }).sessionId;
  const claimedPracticeId = session.user.practiceId;
  if (!sessionId || !claimedPracticeId) {
    throw new AuthError("UNAUTHENTICATED", "You must be logged in.");
  }
  if (await isAdminSessionStale(sessionId)) {
    throw new AuthError(
      "FORBIDDEN",
      "Sign in again before reviewing a reusable template image.",
    );
  }
  try {
    const currentSession = await validateSession({
      sessionToken: sessionId,
      expectedUserId: session.user.id,
      expectedPracticeId: claimedPracticeId,
      allowedRoles: ["ADMIN", "SUPER_ADMIN"],
      requiredProducts: ["TRANSCRIBE_MD"],
    });
    const user = currentSession?.user;
    if (
      !user ||
      (user.role !== "ADMIN" && user.role !== "SUPER_ADMIN") ||
      user.id !== session.user.id ||
      user.practiceId !== claimedPracticeId
    ) {
      throw new AuthError(
        "FORBIDDEN",
        "An active practice administrator is required to review reusable template images.",
      );
    }
    const currentAdmin = await prisma.user.findUnique({
      where: { id: user.id },
      select: {
        id: true,
        email: true,
        role: true,
        practiceId: true,
        products: true,
        isActive: true,
        deactivatedAt: true,
        suspendedAt: true,
        softDeletedAt: true,
        mfaEnabled: true,
        mfaSecret: true,
        mfaVerifiedAt: true,
        practice: {
          select: { id: true, isActive: true, templateTwinEnabled: true },
        },
      },
    });
    const carriesPlatformAdminAuthority =
      currentAdmin?.products.includes("SUPER_ADMIN") === true;
    const hasCompletePlatformMfa =
      currentAdmin !== null && hasCompleteMfaEnrollment(currentAdmin);
    if (
      !currentAdmin ||
      currentAdmin.id !== user.id ||
      currentAdmin.email !== user.email ||
      currentAdmin.practiceId !== user.practiceId ||
      (currentAdmin.role !== "ADMIN" && currentAdmin.role !== "SUPER_ADMIN") ||
      !currentAdmin.isActive ||
      currentAdmin.deactivatedAt !== null ||
      currentAdmin.suspendedAt !== null ||
      currentAdmin.softDeletedAt !== null ||
      !currentAdmin.products.includes("TRANSCRIBE_MD") ||
      currentAdmin.practice.id !== currentAdmin.practiceId ||
      !currentAdmin.practice.isActive ||
      (carriesPlatformAdminAuthority && !hasCompletePlatformMfa)
    ) {
      throw new AuthError(
        "FORBIDDEN",
        "An active practice administrator is required to review reusable template images.",
      );
    }
    const rollout = evaluateTemplateTwinRollout({
      practiceEnabled: currentAdmin.practice.templateTwinEnabled,
    });
    if (!rollout.allowed) {
      throw new AuthError("FORBIDDEN", rollout.reason);
    }
    let rolloutToken;
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
      userId: session.user.id,
      userEmail: currentAdmin.email,
      practiceId: currentAdmin.practiceId,
      role: currentAdmin.role,
      rolloutToken,
    };
  } catch (error) {
    if (error instanceof AuthError) throw error;
    throw new AuthError(
      "FORBIDDEN",
      "Current practice-administrator authorization could not be verified.",
    );
  }
}
