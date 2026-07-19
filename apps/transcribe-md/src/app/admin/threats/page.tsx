// ============================================================================
// /admin/threats — server entry
// ----------------------------------------------------------------------------
// A fresh page/RSC gate runs before threat data is read. This page is the
// actionable face of the detectors that already render as a banner on
// the Overview page: tabs for Active / Resolved / False positives,
// per-threat Investigate drawer, and Resolve / Dismiss workflows.
// ============================================================================

import type { Metadata } from "next";

import { requireFreshPlatformAdminPage } from "@/lib/admin-page-gate";

import AdminThreats from "./_components/AdminThreats.client";
import { getThreatsPageData } from "./_lib/threats-data";

export const metadata: Metadata = {
  title: "Threats · QuillMD Admin",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function ThreatsPage() {
  await requireFreshPlatformAdminPage({ routeKey: "/admin/threats" });
  const initial = await getThreatsPageData();
  return <AdminThreats initial={initial} theme="clinician" />;
}
