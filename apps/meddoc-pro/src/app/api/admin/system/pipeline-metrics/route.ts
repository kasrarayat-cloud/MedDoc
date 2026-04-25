// ============================================================================
// GET /api/admin/system/pipeline-metrics — transcribe-md pipeline KPIs
// ----------------------------------------------------------------------------
// Returns success/failure counts, processing-time percentiles, and
// failure-category breakdowns for the last 24h, 7d, 30d windows.
//
// "Total" = visits in any terminal state (READY, SIGNED, FAILED) whose
// processingFinishedAt falls in the window. We deliberately don't
// count QUEUED visits — they're in-flight, not concluded.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';

interface WindowMetrics {
  total: number;
  succeeded: number;
  failed: number;
  byCategory: Record<string, number>;
  avgProcessingMs: number | null;
  p95ProcessingMs: number | null;
}

interface MetricsRow {
  total: bigint;
  failed: bigint;
  category: string | null;
  category_count: bigint;
  avg_ms: number | null;
  p95_ms: number | null;
}

const WINDOWS = {
  last24h: 24 * 60 * 60 * 1000,
  last7d: 7 * 24 * 60 * 60 * 1000,
  last30d: 30 * 24 * 60 * 60 * 1000,
} as const;

export const dynamic = 'force-dynamic';

export const GET = adminApi('system:pipeline-metrics', async () => {
  const now = new Date();
  const out: Record<string, WindowMetrics> = {};

  for (const [key, ms] of Object.entries(WINDOWS)) {
    const since = new Date(now.getTime() - ms);
    out[key] = await metricsForWindow(since);
  }

  return NextResponse.json(out);
});

async function metricsForWindow(since: Date): Promise<WindowMetrics> {
  // Single $queryRaw to compute all stats in one DB hit. Postgres
  // percentile_cont is the canonical p95; AVG handles the mean.
  // status='SIGNED' counts as succeeded too — a sign requires READY,
  // so the pipeline succeeded earlier.
  const rows = await prisma.$queryRaw<
    {
      total: bigint;
      succeeded: bigint;
      failed: bigint;
      avg_ms: number | null;
      p95_ms: number | null;
    }[]
  >`
    SELECT
      COUNT(*)::bigint AS total,
      COUNT(*) FILTER (WHERE status IN ('READY', 'SIGNED'))::bigint AS succeeded,
      COUNT(*) FILTER (WHERE status = 'FAILED')::bigint AS failed,
      AVG(EXTRACT(EPOCH FROM ("processingFinishedAt" - "processingStartedAt")) * 1000)::float AS avg_ms,
      percentile_cont(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM ("processingFinishedAt" - "processingStartedAt")) * 1000)::float AS p95_ms
    FROM transcribe_visits
    WHERE "processingFinishedAt" >= ${since}
      AND "processingStartedAt" IS NOT NULL
  `;

  const main = rows[0]!;

  // Failure-category breakdown (FAILED rows only, with non-null
  // failureCategory — which the worker writes during the FAILED
  // transition starting from PR #61).
  const catRows = await prisma.$queryRaw<
    { category: string | null; n: bigint }[]
  >`
    SELECT "failureCategory" AS category, COUNT(*)::bigint AS n
    FROM transcribe_visits
    WHERE "processingFinishedAt" >= ${since}
      AND status = 'FAILED'
    GROUP BY "failureCategory"
  `;

  const byCategory: Record<string, number> = {};
  for (const r of catRows) {
    if (r.category != null) byCategory[r.category] = Number(r.n);
  }

  return {
    total: Number(main.total),
    succeeded: Number(main.succeeded),
    failed: Number(main.failed),
    byCategory,
    avgProcessingMs:
      main.avg_ms != null ? Math.round(main.avg_ms) : null,
    p95ProcessingMs:
      main.p95_ms != null ? Math.round(main.p95_ms) : null,
  };
}

// Suppress import-typecheck noise for the unused `MetricsRow` shape
// (kept exported in spirit for client-side typing later).
void ({} as MetricsRow);
