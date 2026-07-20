import { auth } from "@/lib/nextauth";
import {
  adminSurfaceConfigurationError,
  isAdminRequestHost,
  isPhysicianRequestHost,
} from "@/lib/admin-host";
import { verifyFreshPlatformAdminSession } from "@/lib/admin-session-freshness";
import {
  isTemplateTwinAdminAppService,
  isTranscribeMdPhysicianAppService,
} from "@/lib/template-twin/admin-app-service";

export interface MfaRequestActor {
  userId: string;
  sessionId: string | null;
  practiceId: string;
  isAdminHost: boolean;
  isPlatformAdmin: boolean;
}

/**
 * Resolves an MFA actor without turning the admin-host enrollment exception
 * into a clinician route. On the admin host, the current database session,
 * lifecycle, freshness, and Product.SUPER_ADMIN entitlement are mandatory;
 * MFA itself may be absent because enrollment is the purpose of the route.
 */
export async function resolveMfaRequestActor(
  requestHeaders: Pick<Headers, "get">,
): Promise<MfaRequestActor | null> {
  if (adminSurfaceConfigurationError(process.env)) return null;

  // Positively bind the route to one reviewed process/origin pair before
  // parsing a session or consulting current authority. A direct-container or
  // proxy-misrouted request cannot fall through from admin to physician mode.
  const adminSurface =
    isTemplateTwinAdminAppService() && isAdminRequestHost(requestHeaders);
  const physicianSurface =
    isTranscribeMdPhysicianAppService() &&
    isPhysicianRequestHost(requestHeaders);
  if (!adminSurface && !physicianSurface) return null;

  const session = await auth().catch(() => null);
  const userId = session?.user?.id;
  const practiceId = session?.user?.practiceId;
  if (!userId || !practiceId) return null;

  if (adminSurface) {
    const verified = await verifyFreshPlatformAdminSession({
      claimedUserId: userId,
      sessionId: session?.user?.sessionId,
      requireMfa: false,
    });
    if (!verified) return null;
    return {
      userId: verified.userId,
      sessionId: verified.sessionId,
      practiceId: verified.practiceId,
      isAdminHost: true,
      isPlatformAdmin: true,
    };
  }

  return {
    userId,
    sessionId: session?.user?.sessionId ?? null,
    practiceId,
    isAdminHost: false,
    isPlatformAdmin: false,
  };
}
