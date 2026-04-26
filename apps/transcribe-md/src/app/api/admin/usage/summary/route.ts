// ============================================================================
// GET /api/admin/usage/summary — total spend + provider/operation breakdown
// ----------------------------------------------------------------------------
// Query params:
//   window=24h|7d|30d|month   (default 30d)
//
// Response:
//   {
//     window, since, until, totalCostUsd, totalEvents,
//     byProvider:  { deepgram, anthropic, whisper, openai, resend },
//     byOperation: Record<operation, totalCostUsd>,
//     vsLastPeriod: { totalCostUsd, percentChange }
//   }
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';

import { resolveWindow, type WindowKey } from '../../_usage-window';

interface ProvRow {
  provider: string;
  operation: string;
  total: number;
  events: bigint;
}

export const dynamic = 'force-dynamic';

export const GET = adminApi('usage:summary', async (req) => {
  const url = new URL(req.url);
  const window = (url.searchParams.get('window') as WindowKey | null) ?? '30d';
  const w = resolveWindow(window);
  const prev = resolveWindow(window, { offset: 1 });

  const rows = await prisma.$queryRaw<ProvRow[]>`
    SELECT
      provider,
      operation,
      SUM("totalCostUsd")::float AS total,
      COUNT(*)::bigint AS events
    FROM api_usage_events
    WHERE timestamp >= ${w.since} AND timestamp < ${w.until}
    GROUP BY provider, operation
  `.catch(() => [] as ProvRow[]);

  const byProvider: Record<string, number> = {};
  const byOperation: Record<string, number> = {};
  let totalCostUsd = 0;
  let totalEvents = 0;
  for (const r of rows) {
    const cost = Number(r.total ?? 0);
    byProvider[r.provider] = (byProvider[r.provider] ?? 0) + cost;
    byOperation[r.operation] = (byOperation[r.operation] ?? 0) + cost;
    totalCostUsd += cost;
    totalEvents += Number(r.events ?? 0);
  }

  const prevRows = await prisma.$queryRaw<{ total: number }[]>`
    SELECT SUM("totalCostUsd")::float AS total
    FROM api_usage_events
    WHERE timestamp >= ${prev.since} AND timestamp < ${prev.until}
  `.catch(() => [{ total: 0 }] as { total: number }[]);
  const prevTotal = Number(prevRows[0]?.total ?? 0);
  const percentChange =
    prevTotal > 0 ? ((totalCostUsd - prevTotal) / prevTotal) * 100 : null;

  return NextResponse.json({
    window,
    since: w.since.toISOString(),
    until: w.until.toISOString(),
    totalCostUsd: round4(totalCostUsd),
    totalEvents,
    byProvider: roundEach(byProvider),
    byOperation: roundEach(byOperation),
    vsLastPeriod: {
      totalCostUsd: round4(prevTotal),
      percentChange:
        percentChange != null ? Math.round(percentChange * 100) / 100 : null,
    },
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
