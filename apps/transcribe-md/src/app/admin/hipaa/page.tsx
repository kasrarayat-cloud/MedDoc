// ============================================================================
// /admin/hipaa — server entry (Phase 7B)
// ----------------------------------------------------------------------------
// SUPER_ADMIN gate + access audit: requireAdminPage() FIRST (ruling #310 —
// Next 16 skips the layout on an RSC refetch, so it is not relied on).
// SSR fetches every finding (open + resolved) so the tabs render with
// real counts on first paint. Mutations route through /api/admin/hipaa/*
// from the client orchestrator.
// ============================================================================

import type { Metadata } from 'next';

import AdminHipaa from './_components/AdminHipaa.client';
import { getAllFindings } from './_lib/hipaa-data';
import { requireAdminPage } from '../_lib/admin-gate';

export const metadata: Metadata = {
  title: 'HIPAA · QuillMD Admin',
  robots: { index: false, follow: false },
};

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function HipaaPage() {
  await requireAdminPage();
  const findings = await getAllFindings();
  return <AdminHipaa initial={{ findings }} theme="clinician" />;
}
