// ============================================================================
// GET /api/admin/audit-logs/timeline — 24h hourly buckets for charting
// ----------------------------------------------------------------------------
// Response:
//   { buckets: [{ hour: ISO, total, failed }, ...] }
//
// 24 entries always (sparse hours included with zeros) so the client
// can render a fixed-width bar chart without filling gaps client-side.
// Uses Postgres date_trunc('hour', ...) via a single $queryRaw — way
// cheaper than fetching 24 hourly counts via Prisma's groupBy.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';

const WINDOW_HOURS = 24;

export const dynamic = 'force-dynamic';

interface BucketRow {
  hour: Date;
  total: bigint;
  failed: bigint;
}

export const GET = adminApi('audit-logs:timeline', async () => {
  const since = new Date(Date.now() - WINDOW_HOURS * 60 * 60 * 1000);

  // Snap `since` down to the start of the hour so the bucket bounds line
  // up cleanly. The end is "now" — we don't pad to the next full hour
  // because the in-progress bucket is meaningful (it shows current rate).
  const sinceFloor = new Date(since);
  sinceFloor.setMinutes(0, 0, 0);

  const rows = await prisma.$queryRaw<BucketRow[]>`
    SELECT
      date_trunc('hour', "timestamp") AS hour,
      COUNT(*)::bigint AS total,
      SUM(CASE WHEN success = false THEN 1 ELSE 0 END)::bigint AS failed
    FROM audit_logs
    WHERE "timestamp" >= ${sinceFloor}
    GROUP BY 1
    ORDER BY 1 ASC
  `;

  // Build a 24-element array with zero-fills for gap hours. Client
  // never has to think about empty buckets.
  const byHourIso = new Map<string, { total: number; failed: number }>();
  for (const r of rows) {
    byHourIso.set(r.hour.toISOString(), {
      total: Number(r.total),
      failed: Number(r.failed),
    });
  }

  const buckets: { hour: string; total: number; failed: number }[] = [];
  for (let i = 0; i < WINDOW_HOURS; i++) {
    const t = new Date(sinceFloor.getTime() + i * 60 * 60 * 1000);
    const iso = t.toISOString();
    const hit = byHourIso.get(iso);
    buckets.push({
      hour: iso,
      total: hit?.total ?? 0,
      failed: hit?.failed ?? 0,
    });
  }

  return NextResponse.json({ buckets });
});
