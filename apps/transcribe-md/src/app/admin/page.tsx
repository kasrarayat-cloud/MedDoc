// ============================================================================
// Platform-admin overview — server entry
// ----------------------------------------------------------------------------
// This page performs its own fresh host/session/authority/audit gate before
// any cross-practice read. The parent layout is not an authorization boundary.
//
// Initial data is fetched server-side in parallel via the helpers in
// `_lib/dashboard-data.ts` so the page renders fully populated on first
// paint — no client-side loading flash. The only client fetch is the
// SSE subscription, which the client component opens against
// `/api/admin/stream/activity`.
// ============================================================================

import type { Metadata } from "next";

import { requireFreshPlatformAdminPage } from "@/lib/admin-page-gate";

import AdminOverview from "./_components/AdminOverview.client";
import {
  getSystemHealth,
  getRecentActivity,
  getThreats,
  getTimeline,
  getPipelineMetrics,
  getHipaaState,
} from "./_lib/dashboard-data";

export const metadata: Metadata = { title: "Admin · QuillMD" };

// Inherit force-dynamic from the layout. Repeating it here is belt-and-
// braces — a future refactor that drops it from the layout shouldn't
// silently turn this page into a stale static one.
export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function AdminHomePage() {
  const verified = await requireFreshPlatformAdminPage({ routeKey: "/admin" });
  const [systemHealth, activity, threats, timeline, pipeline, hipaa] =
    await Promise.all([
      getSystemHealth(),
      getRecentActivity(30),
      getThreats(),
      getTimeline(),
      getPipelineMetrics(),
      getHipaaState(),
    ]);

  return (
    <AdminOverview
      initial={{ systemHealth, activity, threats, timeline, pipeline, hipaa }}
      userEmail={verified.email ?? "admin"}
      theme="clinician"
    />
  );
}
