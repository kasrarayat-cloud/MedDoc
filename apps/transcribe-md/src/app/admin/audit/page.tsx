// ============================================================================
// /admin/audit — the audit trail, page-shaped
// ----------------------------------------------------------------------------
// Console port (#310 step 3) of meddoc-pro's audit page. transcribe-md already
// had the data — GET /api/admin/audit-logs (+ /stats, /timeline) — and no page
// that called it.
//
// ⚠️ THIS PAGE HOLDS NO DATA AND READS NONE ON THE SERVER, AND THAT IS THE
// GUARD DESIGN, NOT A SHORTCUT. Next's guidance (authentication.md, "do the
// check close to the data") is that a layout does not re-render on client
// navigation, so a page whose data helper leans on the layout's SUPER_ADMIN
// check can serve data on a request that check never saw. Every row here comes
// from `/api/admin/audit-logs`, which is wrapped in `adminApi()` and re-checks
// SUPER_ADMIN, isActive and 12-hour freshness against the database on EVERY
// call, 404-ing anything else. The layout's gate still runs for the shell; the
// data does not depend on it.
// ============================================================================

import type { Metadata } from 'next';

import AdminAudit from './_components/AdminAudit.client';

export const metadata: Metadata = {
  title: 'Audit · QuillMD Admin',
  robots: { index: false, follow: false },
};

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default function AuditPage() {
  return <AdminAudit />;
}
