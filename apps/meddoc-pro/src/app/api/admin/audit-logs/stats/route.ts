// ============================================================================
// GET /api/admin/audit-logs/stats — 24h activity rollup
// ----------------------------------------------------------------------------
// Returns:
//   {
//     windowHours: 24,
//     totalEvents,
//     byAction: { LOGIN_SUCCESS: 45, VISIT_SIGNED: 12, ... },
//     bySuccess: { true: 1200, false: 34 },
//     uniqueUsers
//   }
//
// All queries are practice-unscoped (admin sees everything).
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';

const WINDOW_HOURS = 24;

export const dynamic = 'force-dynamic';

export const GET = adminApi('audit-logs:stats', async () => {
  const since = new Date(Date.now() - WINDOW_HOURS * 60 * 60 * 1000);

  const [byAction, bySuccessGroup, uniqueUsersResult, totalEvents] =
    await Promise.all([
      prisma.auditLog.groupBy({
        by: ['action'],
        where: { timestamp: { gte: since } },
        _count: { _all: true },
      }),
      prisma.auditLog.groupBy({
        by: ['success'],
        where: { timestamp: { gte: since } },
        _count: { _all: true },
      }),
      prisma.auditLog.findMany({
        where: { timestamp: { gte: since }, userId: { not: null } },
        select: { userId: true },
        distinct: ['userId'],
      }),
      prisma.auditLog.count({ where: { timestamp: { gte: since } } }),
    ]);

  const byActionObj: Record<string, number> = {};
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  for (const row of byAction as any[]) {
    byActionObj[String(row.action)] = (row._count?._all as number) ?? 0;
  }
  const bySuccessObj: { true: number; false: number } = { true: 0, false: 0 };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  for (const row of bySuccessGroup as any[]) {
    if (row.success === true) bySuccessObj.true = row._count?._all ?? 0;
    if (row.success === false) bySuccessObj.false = row._count?._all ?? 0;
  }

  return NextResponse.json({
    windowHours: WINDOW_HOURS,
    totalEvents,
    byAction: byActionObj,
    bySuccess: bySuccessObj,
    uniqueUsers: uniqueUsersResult.length,
  });
});
