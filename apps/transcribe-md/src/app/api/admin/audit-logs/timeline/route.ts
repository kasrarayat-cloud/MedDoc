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
import { resolveAuditWindow } from '../../_audit-window';

export const dynamic = 'force-dynamic';

interface BucketRow {
  hour: Date;
  total: bigint;
  failed: bigint;
}

export const GET = adminApi('audit-logs:timeline', async () => {
  // Phase 7A: shared window so this endpoint + /audit-logs/stats agree
  // on what "last 24 hours" means. The bucket loop below ends at the
  // current partial hour (rightmost bucket = "this hour so far").
  const w = resolveAuditWindow(24);

  const rows = await prisma.$queryRaw<BucketRow[]>`
    SELECT
      date_trunc('hour', "timestamp") AS hour,
      COUNT(*)::bigint AS total,
      SUM(CASE WHEN success = false THEN 1 ELSE 0 END)::bigint AS failed
    FROM audit_logs
    WHERE "timestamp" >= ${w.since}
    GROUP BY 1
    ORDER BY 1 ASC
  `;

  // Build an N-element array with zero-fills for gap hours. Client
  // never has to think about empty buckets.
  const byHourIso = new Map<string, { total: number; failed: number }>();
  for (const r of rows) {
    byHourIso.set(r.hour.toISOString(), {
      total: Number(r.total),
      failed: Number(r.failed),
    });
  }

  const buckets: { hour: string; total: number; failed: number }[] = [];
  for (let i = 0; i < w.hours; i++) {
    const t = new Date(w.since.getTime() + i * 60 * 60 * 1000);
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
