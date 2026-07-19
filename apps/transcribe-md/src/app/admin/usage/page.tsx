// ============================================================================
// /admin/usage — server entry
// ----------------------------------------------------------------------------
// Fresh authorization and required access-audit persistence run in this page
// before the four cross-practice data slices are read.
// ============================================================================

import type { Metadata } from "next";

import { requireFreshPlatformAdminPage } from "@/lib/admin-page-gate";

import AdminUsage from "./_components/AdminUsage.client";
import {
  fetchAnomalies,
  fetchTimeline,
  fetchTopUsers,
  fetchUsageSummary,
} from "./_lib/usage-data";

export const metadata: Metadata = {
  title: "API Usage · QuillMD Admin",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function UsagePage() {
  await requireFreshPlatformAdminPage({ routeKey: "/admin/usage" });
  const [summary, timeline, topUsers, anomalies] = await Promise.all([
    fetchUsageSummary("month"),
    fetchTimeline("month"),
    fetchTopUsers("month", 10),
    fetchAnomalies(),
  ]);

  return (
    <AdminUsage
      initial={{ summary, timeline, topUsers, anomalies }}
      theme="clinician"
    />
  );
}
