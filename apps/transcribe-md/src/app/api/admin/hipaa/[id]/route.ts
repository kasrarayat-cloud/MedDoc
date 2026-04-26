// ============================================================================
// GET /api/admin/hipaa/[id] — Phase 7B single HIPAA finding detail
// ----------------------------------------------------------------------------
// Returns the same shape as the list endpoint's per-row payload, plus the
// chain of audit_logs rows referencing this finding (HIPAA_FINDING_RESOLVED
// + HIPAA_FINDING_REOPENED) so the future detail UI can render a timeline.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';

export const dynamic = 'force-dynamic';

export const GET = adminApi('hipaa:detail', async (req) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  const id = segs[segs.indexOf('hipaa') + 1];
  if (!id) return NextResponse.json({ error: 'Bad path' }, { status: 400 });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const row: any = await (prisma as any).hipaaFinding.findUnique({
    where: { id },
    select: {
      id: true,
      control: true,
      severity: true,
      title: true,
      detail: true,
      status: true,
      resolvedAt: true,
      resolvedById: true,
      resolvedByEmail: true,
      resolutionNote: true,
      createdAt: true,
      updatedAt: true,
    },
  });
  if (!row) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  // Audit timeline for this finding — HIPAA_FINDING_* actions targeting
  // this id. Newest first.
  const timeline = await prisma.auditLog.findMany({
    where: {
      targetType: 'HipaaFinding',
      targetId: id,
    },
    orderBy: [{ timestamp: 'desc' }, { id: 'desc' }],
    take: 50,
    select: {
      id: true,
      timestamp: true,
      action: true,
      userEmailSnapshot: true,
      metadata: true,
    },
  });

  return NextResponse.json({
    finding: {
      id: row.id,
      control: row.control,
      severity: row.severity,
      title: row.title,
      detail: row.detail ?? null,
      status: row.status,
      resolvedAt: row.resolvedAt?.toISOString() ?? null,
      resolvedById: row.resolvedById ?? null,
      resolvedByEmail: row.resolvedByEmail ?? null,
      resolutionNote: row.resolutionNote ?? null,
      createdAt: row.createdAt.toISOString(),
      updatedAt: row.updatedAt.toISOString(),
    },
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    timeline: timeline.map((t: any) => ({
      id: t.id,
      timestamp: t.timestamp.toISOString(),
      action: t.action,
      actorEmail: t.userEmailSnapshot ?? null,
      metadata: t.metadata ?? null,
    })),
  });
});
