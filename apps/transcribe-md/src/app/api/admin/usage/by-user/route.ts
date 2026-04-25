// ============================================================================
// GET /api/admin/usage/by-user — top users by spend in the chosen window
// ----------------------------------------------------------------------------
// Query params:
//   window=24h|7d|30d|month   (default 30d)
//   limit=N                   (default 50, max 200)
//   sortBy=cost|events        (default cost)
//
// Response:
//   { window, since, until, rows: [{ userId, userEmail, totalCostUsd, events }] }
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';

import { resolveWindow, type WindowKey } from '../../_usage-window';

interface Row {
  userId: string | null;
  userEmail: string | null;
  total: number;
  events: bigint;
}

export const dynamic = 'force-dynamic';

export const GET = adminApi('usage:by-user', async (req) => {
  const url = new URL(req.url);
  const window = (url.searchParams.get('window') as WindowKey | null) ?? '30d';
  const limitRaw = Number.parseInt(url.searchParams.get('limit') ?? '50', 10);
  const limit = Number.isFinite(limitRaw) && limitRaw > 0 ? Math.min(limitRaw, 200) : 50;
  const sortBy = url.searchParams.get('sortBy') === 'events' ? 'events' : 'cost';
  const w = resolveWindow(window);

  // LEFT JOIN to users so we can surface the email for the dashboard
  // even when the userId column on api_usage_events is the source of
  // truth. Nullable userId rows aggregate under "(unattributed)".
  const rows =
    sortBy === 'events'
      ? await prisma.$queryRaw<Row[]>`
          SELECT e."userId" AS "userId",
                 u.email   AS "userEmail",
                 SUM(e."totalCostUsd")::float AS total,
                 COUNT(*)::bigint              AS events
          FROM api_usage_events e
          LEFT JOIN users u ON u.id = e."userId"
          WHERE e.timestamp >= ${w.since} AND e.timestamp < ${w.until}
          GROUP BY e."userId", u.email
          ORDER BY events DESC, total DESC
          LIMIT ${limit}
        `.catch(() => [] as Row[])
      : await prisma.$queryRaw<Row[]>`
          SELECT e."userId" AS "userId",
                 u.email   AS "userEmail",
                 SUM(e."totalCostUsd")::float AS total,
                 COUNT(*)::bigint              AS events
          FROM api_usage_events e
          LEFT JOIN users u ON u.id = e."userId"
          WHERE e.timestamp >= ${w.since} AND e.timestamp < ${w.until}
          GROUP BY e."userId", u.email
          ORDER BY total DESC, events DESC
          LIMIT ${limit}
        `.catch(() => [] as Row[]);

  return NextResponse.json({
    window,
    since: w.since.toISOString(),
    until: w.until.toISOString(),
    sortBy,
    rows: rows.map((r: Row) => ({
      userId: r.userId,
      userEmail: r.userEmail ?? (r.userId ? '(deleted user)' : '(unattributed)'),
      totalCostUsd: Math.round((Number(r.total) || 0) * 10_000) / 10_000,
      events: Number(r.events ?? 0),
    })),
  });
});
