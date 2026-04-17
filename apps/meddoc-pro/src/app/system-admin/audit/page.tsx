// ============================================================================
// System Admin — Security Logs (system-wide audit trail)
// ----------------------------------------------------------------------------
// Reuses the dashboard AuditLogTable but pulls a larger window (2k events)
// for system-wide review. ADMIN-only access is already enforced by the
// /system-admin layout; this page just fetches and renders.
// ============================================================================

import { getAuditLogs } from '@/lib/audit';
import { getSession } from '@/lib/auth';
import AuditLogTable from '@/app/dashboard/audit/AuditLogTable';

export const dynamic = 'force-dynamic';

export default async function SystemAdminAuditPage() {
  const session = await getSession();
  if (!session) return null; // layout gate already guarantees this
  const logs = await getAuditLogs(session, 2000);

  return <AuditLogTable logs={logs} />;
}
