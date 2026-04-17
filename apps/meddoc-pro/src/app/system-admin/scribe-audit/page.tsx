// ============================================================================
// System Admin — Scribe audit trail (M7)
// ----------------------------------------------------------------------------
// Reads ScribeAuditEvent rows (separate table from AuditLog — M1 D3 kept
// the medical-legal diff payload distinct). ADMIN sees own practice,
// SUPER_ADMIN sees all. Last 500 rows; client-side filtering on top.
// ============================================================================

import prisma from '@meddoc/db';
import { getSession } from '@/lib/auth';
import { canBypassTenantScope, tenantScope } from '@meddoc/auth';
import ScribeAuditTable, { type ScribeAuditRow } from './ScribeAuditTable';

export const dynamic = 'force-dynamic';

export default async function ScribeAuditPage() {
  const session = await getSession();
  if (!session) return null; // layout already gates

  const where = canBypassTenantScope(session) ? {} : tenantScope(session);

  const rows = await prisma.scribeAuditEvent.findMany({
    where,
    orderBy: { createdAt: 'desc' },
    take: 500,
    select: {
      id: true,
      practiceId: true,
      visitId: true,
      actorId: true,
      action: true,
      diff: true,
      createdAt: true,
    },
  });

  // Pre-stringify for serialization to the client component — Prisma
  // returns Date objects and nested JSONB values that would need
  // careful passthrough otherwise.
  const serialized: ScribeAuditRow[] = rows.map(
    (r: {
      id: string;
      practiceId: string;
      visitId: string;
      actorId: string;
      action: string;
      diff: unknown;
      createdAt: Date;
    }) => ({
      id: r.id,
      practiceId: r.practiceId,
      visitId: r.visitId,
      actorId: r.actorId,
      action: r.action,
      diff: r.diff ?? null,
      createdAt: r.createdAt.toISOString(),
    })
  );

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Scribe audit log</h1>
        <p className="text-sm text-slate-400 mt-1">
          ScribeAuditEvent rows — every action on a ScribeVisit (transcription
          started / finished, WS connected, SOAP generated, output errored, sign
          pushed, retry, etc.). Showing the newest {serialized.length} events;
          filter below to narrow.
        </p>
      </div>
      <ScribeAuditTable rows={serialized} />
    </div>
  );
}
