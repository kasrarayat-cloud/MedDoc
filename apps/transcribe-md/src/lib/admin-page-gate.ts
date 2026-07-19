import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { auth } from "@/lib/nextauth";
import { logRequiredAdminAudit } from "@/lib/audit";
import { isAdminRequestHost } from "@/lib/admin-host";
import {
  verifyFreshPlatformAdminSession,
  type VerifiedPlatformAdminSession,
} from "@/lib/admin-session-freshness";

interface RequirePlatformAdminPageInput {
  routeKey: string;
  /** Only the isolated enrollment page may set this false. */
  requireMfa?: boolean;
}

/**
 * Fresh page/RSC authorization primitive. Every admin page invokes this in
 * its own render before any protected data read; it deliberately does not
 * rely on a parent layout, which Next may reuse during client navigation.
 */
export async function requireFreshPlatformAdminPage(
  input: RequirePlatformAdminPageInput,
): Promise<VerifiedPlatformAdminSession> {
  const requestHeaders = await headers();
  if (!isAdminRequestHost(requestHeaders)) notFound();

  const session = await auth().catch(() => null);
  const verified = await verifyFreshPlatformAdminSession({
    claimedUserId: session?.user?.id,
    sessionId: session?.user?.sessionId,
    requireMfa: input.requireMfa,
  });
  if (!verified) notFound();

  try {
    await logRequiredAdminAudit({
      action: "ADMIN_DASHBOARD_ACCESS",
      userId: verified.userId,
      userEmail: verified.email,
      practiceId: verified.practiceId,
      targetType: "AdminPage",
      targetId: input.routeKey,
      metadata: {
        path: input.routeKey,
        sessionCreatedAt: verified.sessionCreatedAt.toISOString(),
      },
    });
  } catch {
    console.error(
      `[admin-page:${input.routeKey}] required access audit failed; request denied`,
    );
    notFound();
  }

  return verified;
}
