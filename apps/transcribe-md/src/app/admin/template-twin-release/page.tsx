import type { Metadata } from "next";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { isAdminRequestHost } from "@/lib/admin-host";
import { verifyFreshPlatformAdminSession } from "@/lib/admin-session-freshness";
import { auth } from "@/lib/nextauth";
import { inspectTemplateTwinReleaseControl } from "@/lib/template-twin/release-control";
import { templateTwinReleaseControlProcessEnabled } from "@/lib/template-twin/release-control-db";

import TemplateTwinReleaseWorkbench from "./_components/TemplateTwinReleaseWorkbench.client";

export const metadata: Metadata = {
  title: "Template Twin release · QuillMD Admin",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function TemplateTwinReleasePage() {
  if (!templateTwinReleaseControlProcessEnabled()) notFound();
  // Layouts are cached across client navigation in Next 16. This page owns a
  // fresh request gate so revoked/expired operators cannot receive release,
  // practice, or approval data from a later RSC navigation.
  if (!isAdminRequestHost(await headers())) notFound();
  const session = await auth().catch(() => null);
  const verified = await verifyFreshPlatformAdminSession({
    claimedUserId: session?.user?.id,
    sessionId: session?.user?.sessionId,
  });
  if (!verified) notFound();
  const initial = await inspectTemplateTwinReleaseControl({
    operatorUserId: verified.userId,
  });
  return <TemplateTwinReleaseWorkbench initial={initial} />;
}
