import { auth } from "@/lib/nextauth";
import {
  adminSurfaceConfigurationError,
  isAdminRequestHost,
} from "@/lib/admin-host";
import { verifyFreshPlatformAdminSession } from "@/lib/admin-session-freshness";

export interface MfaRequestActor {
  userId: string;
  sessionId: string | null;
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

  const session = await auth().catch(() => null);
  const userId = session?.user?.id;
  if (!userId) return null;

  if (isAdminRequestHost(requestHeaders)) {
    const verified = await verifyFreshPlatformAdminSession({
      claimedUserId: userId,
      sessionId: session?.user?.sessionId,
      requireMfa: false,
    });
    if (!verified) return null;
    return {
      userId: verified.userId,
      sessionId: verified.sessionId,
      isAdminHost: true,
      isPlatformAdmin: true,
    };
  }

  return {
    userId,
    sessionId: session?.user?.sessionId ?? null,
    isAdminHost: false,
    isPlatformAdmin: false,
  };
}
