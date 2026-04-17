// ============================================================================
// Audit Logs — Server Component (HIPAA §164.312(b) Compliance Dashboard)
// ============================================================================

import { redirect } from 'next/navigation';
import { requireRole, AuthError } from '@/lib/auth';
import { getAuditLogs } from '@/lib/audit';
import AuditLogTable from './AuditLogTable';

export const dynamic = 'force-dynamic';

export default async function AuditPage() {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    if (err instanceof AuthError) redirect('/login');
    throw err;
  }

  const logs = await getAuditLogs(session, 500);

  return <AuditLogTable logs={logs} />;
}
