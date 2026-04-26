// ============================================================================
// GET /api/admin/usage/for-user/[userId] — single-user usage breakdown
// ----------------------------------------------------------------------------
// Query params:
//   window=24h|7d|30d|month   (default 30d)
//
// Response:
//   { userId, window, totalCostUsd, byProvider, byOperation, recent: [...] }
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';

import { resolveWindow, type WindowKey } from '../../../_usage-window';

interface AggRow {
  provider: string;
  operation: string;
  total: number;
  events: bigint;
}

interface RecentRow {
  id: string;
  timestamp: Date;
  provider: string;
  operation: string;
  totalCostUsd: number;
  inputTokens: number | null;
  outputTokens: number | null;
  audioSeconds: number | null;
  emailCount: number | null;
  visitId: string | null;
  modelName: string | null;
}

export const dynamic = 'force-dynamic';

export const GET = adminApi('usage:for-user', async (req) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  // .../api/admin/usage/for-user/<userId>
  const userId = segs[segs.indexOf('for-user') + 1];
  if (!userId) {
    return NextResponse.json({ error: 'Bad path' }, { status: 400 });
  }

  const url = new URL(req.url);
  const window = (url.searchParams.get('window') as WindowKey | null) ?? '30d';
  const w = resolveWindow(window);

  const [aggRows, recentRows] = await Promise.all([
    prisma.$queryRaw<AggRow[]>`
      SELECT provider,
             operation,
             SUM("totalCostUsd")::float AS total,
             COUNT(*)::bigint           AS events
      FROM api_usage_events
      WHERE "userId" = ${userId}
        AND timestamp >= ${w.since} AND timestamp < ${w.until}
      GROUP BY provider, operation
    `.catch(() => [] as AggRow[]),
    prisma.$queryRaw<RecentRow[]>`
      SELECT id, timestamp, provider, operation,
             "totalCostUsd", "inputTokens", "outputTokens",
             "audioSeconds", "emailCount", "visitId", "modelName"
      FROM api_usage_events
      WHERE "userId" = ${userId}
        AND timestamp >= ${w.since} AND timestamp < ${w.until}
      ORDER BY timestamp DESC
      LIMIT 25
    `.catch(() => [] as RecentRow[]),
  ]);

  const byProvider: Record<string, number> = {};
  const byOperation: Record<string, number> = {};
  let totalCostUsd = 0;
  let totalEvents = 0;
  for (const r of aggRows) {
    const cost = Number(r.total ?? 0);
    byProvider[r.provider] = (byProvider[r.provider] ?? 0) + cost;
    byOperation[r.operation] = (byOperation[r.operation] ?? 0) + cost;
    totalCostUsd += cost;
    totalEvents += Number(r.events ?? 0);
  }

  return NextResponse.json({
    userId,
    window,
    since: w.since.toISOString(),
    until: w.until.toISOString(),
    totalCostUsd: round4(totalCostUsd),
    totalEvents,
    byProvider: roundEach(byProvider),
    byOperation: roundEach(byOperation),
    recent: recentRows.map((r: RecentRow) => ({
      id: r.id,
      timestamp: r.timestamp.toISOString(),
      provider: r.provider,
      operation: r.operation,
      totalCostUsd: round4(Number(r.totalCostUsd)),
      inputTokens: r.inputTokens,
      outputTokens: r.outputTokens,
      audioSeconds: r.audioSeconds,
      emailCount: r.emailCount,
      visitId: r.visitId,
      modelName: r.modelName,
    })),
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
