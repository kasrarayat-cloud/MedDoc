// ============================================================================
// /admin/threats — server entry
// ----------------------------------------------------------------------------
// SUPER_ADMIN gate: requireAdminPage() FIRST (ruling #310 — the layout is
// skipped on an RSC refetch, so it is not relied on). This page is the
// actionable face of the detectors that already render as a banner on
// the Overview page: tabs for Active / Resolved / False positives,
// per-threat Investigate drawer, and Resolve / Dismiss workflows.
// ============================================================================

import type { Metadata } from 'next';

import AdminThreats from './_components/AdminThreats.client';
import { getThreatsPageData } from './_lib/threats-data';
import { requireAdminPage } from '../_lib/admin-gate';

export const metadata: Metadata = {
  title: 'Threats · QuillMD Admin',
  robots: { index: false, follow: false },
};

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function ThreatsPage() {
  await requireAdminPage();
  const initial = await getThreatsPageData();
  return <AdminThreats initial={initial} theme="clinician" />;
}
