// ============================================================================
// /admin/usage — server entry
// ----------------------------------------------------------------------------
// SUPER_ADMIN gate + access audit log inherited from /admin/layout.tsx.
// This page just fetches the four data slices in parallel and hands
// them to the client orchestrator.
// ============================================================================

import type { Metadata } from 'next';

import AdminUsage from './_components/AdminUsage.client';
import {
  fetchAnomalies,
  fetchTimeline,
  fetchTopUsers,
  fetchUsageSummary,
} from './_lib/usage-data';

export const metadata: Metadata = {
  title: 'API Usage · QuillMD Admin',
  robots: { index: false, follow: false },
};

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function UsagePage() {
  const [summary, timeline, topUsers, anomalies] = await Promise.all([
    fetchUsageSummary('month'),
    fetchTimeline('month'),
    fetchTopUsers('month', 10),
    fetchAnomalies(),
  ]);

  return (
    <AdminUsage
      initial={{ summary, timeline, topUsers, anomalies }}
    />
  );
}
