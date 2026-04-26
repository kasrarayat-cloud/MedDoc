// ============================================================================
// /admin/hipaa — server-side data fetcher (Phase 7B)
// ----------------------------------------------------------------------------
// Mirror of how /admin/threats/_lib/threats-data.ts shells out to the
// dashboard data layer — only this one is a thin wrapper around a single
// Prisma query, so it lives here without going through dashboard-data.
// ============================================================================

import 'server-only';

import prisma from '@meddoc/db';

import type { HipaaFindingRow } from '../_types';

const SEVERITY_RANK: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

export async function getAllFindings(): Promise<HipaaFindingRow[]> {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const rows: any[] = await (prisma as any).hipaaFinding.findMany({
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

    // Sort: open before resolved; within each group, severity rank
    // (critical → low) then most recent first.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    rows.sort((a: any, b: any) => {
      const aResolved = a.status === 'resolved' ? 1 : 0;
      const bResolved = b.status === 'resolved' ? 1 : 0;
      if (aResolved !== bResolved) return aResolved - bResolved;
      const sevDiff =
        (SEVERITY_RANK[a.severity] ?? 99) - (SEVERITY_RANK[b.severity] ?? 99);
      if (sevDiff !== 0) return sevDiff;
      if (aResolved === 1) {
        return (b.resolvedAt?.getTime() ?? 0) - (a.resolvedAt?.getTime() ?? 0);
      }
      return b.createdAt.getTime() - a.createdAt.getTime();
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return rows.map((r: any) => ({
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
  } catch (err) {
    console.error('[admin/hipaa] getAllFindings failed:', err);
    return [];
  }
}
