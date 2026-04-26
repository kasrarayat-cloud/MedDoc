// ============================================================================
// GET /api/admin/usage/timeline — time-bucketed spend for charting
// ----------------------------------------------------------------------------
// Query params:
//   window=24h|7d|30d|month            (default 7d)
//   granularity=hour|day               (default: hour for 24h, else day)
//
// Response:
//   { window, granularity, buckets: [{ time, totalCostUsd, events,
//     byProvider: {deepgram, anthropic, ...} }] }
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';

import { resolveWindow, type WindowKey } from '../../_usage-window';

interface Row {
  bucket: Date;
  provider: string;
  total: number;
  events: bigint;
}

export const dynamic = 'force-dynamic';

export const GET = adminApi('usage:timeline', async (req) => {
  const url = new URL(req.url);
  const window = (url.searchParams.get('window') as WindowKey | null) ?? '7d';
  const granularity =
    url.searchParams.get('granularity') === 'day'
      ? 'day'
      : url.searchParams.get('granularity') === 'hour'
        ? 'hour'
        : window === '24h'
          ? 'hour'
          : 'day';
  const w = resolveWindow(window);

  const rows =
    granularity === 'hour'
      ? await prisma.$queryRaw<Row[]>`
          SELECT date_trunc('hour', timestamp) AS bucket,
                 provider,
                 SUM("totalCostUsd")::float    AS total,
                 COUNT(*)::bigint              AS events
          FROM api_usage_events
          WHERE timestamp >= ${w.since} AND timestamp < ${w.until}
          GROUP BY 1, 2
          ORDER BY 1 ASC
        `.catch(() => [] as Row[])
      : await prisma.$queryRaw<Row[]>`
          SELECT date_trunc('day', timestamp) AS bucket,
                 provider,
                 SUM("totalCostUsd")::float   AS total,
                 COUNT(*)::bigint             AS events
          FROM api_usage_events
          WHERE timestamp >= ${w.since} AND timestamp < ${w.until}
          GROUP BY 1, 2
          ORDER BY 1 ASC
        `.catch(() => [] as Row[]);

  // Pivot into per-bucket entries with byProvider sub-objects.
  type Entry = {
    time: string;
    totalCostUsd: number;
    events: number;
    byProvider: Record<string, number>;
  };
  const entries = new Map<string, Entry>();
  for (const r of rows) {
    const t = r.bucket.toISOString();
    const e: Entry =
      entries.get(t) ?? {
        time: t,
        totalCostUsd: 0,
        events: 0,
        byProvider: {} as Record<string, number>,
      };
    const cost = Number(r.total ?? 0);
    e.totalCostUsd += cost;
    e.events += Number(r.events ?? 0);
    e.byProvider[r.provider] =
      (e.byProvider[r.provider] ?? 0) + cost;
    entries.set(t, e);
  }
  const buckets = Array.from(entries.values()).map((e) => ({
    ...e,
    totalCostUsd: round4(e.totalCostUsd),
    byProvider: roundEach(e.byProvider),
  }));

  return NextResponse.json({
    window,
    granularity,
    since: w.since.toISOString(),
    until: w.until.toISOString(),
    buckets,
  });
});

function round4(n: number) {
  return Math.round(n * 10_000) / 10_000;
}
function roundEach(o: Record<string, number>): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [k, v] of Object.entries(o)) out[k] = round4(v);
  return out;
}
