// ============================================================================
// Platform-admin overview — server entry
// ----------------------------------------------------------------------------
// SUPER_ADMIN gate + access audit log live in `layout.tsx` (defense-in-
// depth). This page assumes both have already run.
//
// Initial data is fetched server-side in parallel via the helpers in
// `_lib/dashboard-data.ts` so the page renders fully populated on first
// paint — no client-side loading flash. The only client fetch is the
// SSE subscription, which the client component opens against
// `/api/admin/stream/activity`.
// ============================================================================

import type { Metadata } from 'next';

import { auth } from '@/lib/nextauth';

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
  const [session, systemHealth, activity, threats, timeline, pipeline, hipaa] = await Promise.all([
    auth().catch(() => null),
    getSystemHealth(),
    getRecentActivity(30),
    getThreats(),
    getTimeline(),
    getPipelineMetrics(),
    getHipaaState(),
  ]);

  const userEmail = session?.user?.email ?? 'admin';

  return (
    <AdminOverview
      initial={{ systemHealth, activity, threats, timeline, pipeline, hipaa }}
      userEmail={userEmail}
      theme="clinician"
    />
  );
}
