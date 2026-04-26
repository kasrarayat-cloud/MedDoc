// ============================================================================
// GET /api/admin/hipaa — Phase 7B HIPAA findings list
// ----------------------------------------------------------------------------
// Query param:
//   status = 'open' | 'resolved' | 'all'   (default 'all')
//
// Response:
//   { findings: HipaaFindingRow[] }
//
// Sorted: open first (severity desc — critical → high → medium → low →
// other), then resolved (most recently resolved first).
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';

const QuerySchema = z.object({
  status: z.enum(['open', 'resolved', 'all']).optional(),
});

interface HipaaFindingRow {
  id: string;
  control: string;
  severity: string;
  title: string;
  detail: string | null;
  status: string;
  resolvedAt: string | null;
  resolvedById: string | null;
  resolvedByEmail: string | null;
  resolutionNote: string | null;
  createdAt: string;
  updatedAt: string;
}

const SEVERITY_RANK: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

export const dynamic = 'force-dynamic';

export const GET = adminApi('hipaa:list', async (req) => {
  const url = new URL(req.url);
  const parsed = QuerySchema.safeParse({
    status: url.searchParams.get('status') ?? undefined,
  });
  if (!parsed.success) {
    return NextResponse.json({ error: 'Invalid query' }, { status: 400 });
  }
  const status = parsed.data.status ?? 'all';

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const where: any = {};
  if (status === 'open') where.status = { not: 'resolved' };
  else if (status === 'resolved') where.status = 'resolved';

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rows: any[] = await (prisma as any).hipaaFinding.findMany({
    where,
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

  // Sort: status (open before resolved), then severity rank, then
  // most-recent createdAt within each group.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  rows.sort((a: any, b: any) => {
    const aOpen = a.status !== 'resolved' ? 0 : 1;
    const bOpen = b.status !== 'resolved' ? 0 : 1;
    if (aOpen !== bOpen) return aOpen - bOpen;
    const sevDiff = (SEVERITY_RANK[a.severity] ?? 99) - (SEVERITY_RANK[b.severity] ?? 99);
    if (sevDiff !== 0) return sevDiff;
    if (aOpen === 1) {
      // resolved: newest resolution first
      return (b.resolvedAt?.getTime() ?? 0) - (a.resolvedAt?.getTime() ?? 0);
    }
    return b.createdAt.getTime() - a.createdAt.getTime();
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const findings: HipaaFindingRow[] = rows.map((r: any) => ({
    id: r.id,
    control: r.control,
    severity: r.severity,
    title: r.title,
    detail: r.detail ?? null,
    status: r.status,
    resolvedAt: r.resolvedAt?.toISOString() ?? null,
    resolvedById: r.resolvedById ?? null,
    resolvedByEmail: r.resolvedByEmail ?? null,
    resolutionNote: r.resolutionNote ?? null,
    createdAt: r.createdAt.toISOString(),
    updatedAt: r.updatedAt.toISOString(),
  }));

  return NextResponse.json({ findings });
});
