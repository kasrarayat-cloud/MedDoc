// ============================================================================
// Platform-admin overview — server entry
// ----------------------------------------------------------------------------
// SUPER_ADMIN gate + access audit: requireAdminPage() FIRST. The layout
// gates too, but Next 16 skips the layout on an RSC refetch (ruling
// #310), so this page never assumes it ran.
//
// Initial data is fetched server-side in parallel via the helpers in
// `_lib/dashboard-data.ts` so the page renders fully populated on first
// paint — no client-side loading flash. The only client fetch is the
// SSE subscription, which the client component opens against
// `/api/admin/stream/activity`.
// ============================================================================

import type { Metadata } from 'next';

import { requireAdminPage } from './_lib/admin-gate';

import AdminOverview from './_components/AdminOverview.client';
import {
  getSystemHealth,
  getRecentActivity,
  getThreats,
  getTimeline,
  getPipelineMetrics,
  getHipaaState,
} from './_lib/dashboard-data';

export const metadata: Metadata = { title: 'Admin · QuillMD' };

// Inherit force-dynamic from the layout. Repeating it here is belt-and-
// braces — a future refactor that drops it from the layout shouldn't
// silently turn this page into a stale static one.
export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function AdminHomePage() {
  const session = await requireAdminPage();
  const [systemHealth, activity, threats, timeline, pipeline, hipaa] = await Promise.all([
    getSystemHealth(),
    getRecentActivity(30),
    getThreats(),
    getTimeline(),
    getPipelineMetrics(),
    getHipaaState(),
  ]);

  const userEmail = session.user.email ?? 'admin';

  return (
    <AdminOverview
      initial={{ systemHealth, activity, threats, timeline, pipeline, hipaa }}
      userEmail={userEmail}
      theme="clinician"
    />
  );
}
