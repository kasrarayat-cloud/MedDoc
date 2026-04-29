// ============================================================================
// /admin/hipaa — server entry (Phase 7B)
// ----------------------------------------------------------------------------
// SUPER_ADMIN gate + access audit log inherited from /admin/layout.tsx.
// SSR fetches every finding (open + resolved) so the tabs render with
// real counts on first paint. Mutations route through /api/admin/hipaa/*
// from the client orchestrator.
// ============================================================================

import type { Metadata } from 'next';

import AdminHipaa from './_components/AdminHipaa.client';
import { getAllFindings } from './_lib/hipaa-data';

export const metadata: Metadata = {
  title: 'HIPAA · QuillMD Admin',
  robots: { index: false, follow: false },
};

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function HipaaPage() {
  const findings = await getAllFindings();
  return <AdminHipaa initial={{ findings }} theme="clinician" />;
}
