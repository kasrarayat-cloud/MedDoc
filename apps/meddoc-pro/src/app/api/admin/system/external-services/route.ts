// ============================================================================
// GET /api/admin/system/external-services — Deepgram / Anthropic /
// OpenAI / Resend liveness from existing call records
// ----------------------------------------------------------------------------
// We don't ping the upstreams ourselves — that would (a) cost money
// (Anthropic + Deepgram charge per call) and (b) give a useless
// answer (the upstream might be up and we can still be down).
// Instead we read the existing `ai_calls` and `audit_logs` tables and
// derive last-success / last-failure / 24h-error-rate / latency P95.
//
// Shape:
//   { deepgram: {...}, anthropic: {...}, openai: {...}, resend: {...} }
//
// Each section is null when we have zero records in the 24h window.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';

interface ServiceMetrics {
  lastSuccessAt: string | null;
  lastFailureAt: string | null;
  errorRate24h: number;
  latencyP95Ms: number | null;
  callCount24h: number;
}

export const dynamic = 'force-dynamic';

export const GET = adminApi('system:external-services', async () => {
  const since = new Date(Date.now() - 24 * 60 * 60 * 1000);

  const [deepgram, anthropic, openai, resend] = await Promise.all([
    metricsForProvider('deepgram', since),
    metricsForProvider('anthropic', since),
    metricsForProvider('openai', since),
    resendMetrics(since),
  ]);

  return NextResponse.json({ deepgram, anthropic, openai, resend });
});

async function metricsForProvider(
  provider: string,
  since: Date
): Promise<ServiceMetrics | null> {
  // ai_calls schema: provider (text), succeeded (bool), latencyMs (int),
  // createdAt (timestamp), errorClass (text). Fields exist on AiCall —
  // see schema.prisma for the model. We use $queryRaw because Prisma's
  // typed client surface for AiCall is `any`-typed in the workspace
  // (per the memory note on shared prisma export).
  const rows = await prisma.$queryRaw<
    {
      total: bigint;
      succeeded: bigint;
      failed: bigint;
      last_success_at: Date | null;
      last_failure_at: Date | null;
      p95_ms: number | null;
    }[]
  >`
    SELECT
      COUNT(*)::bigint AS total,
      COUNT(*) FILTER (WHERE success = true)::bigint AS succeeded,
      COUNT(*) FILTER (WHERE success = false)::bigint AS failed,
      MAX("createdAt") FILTER (WHERE success = true) AS last_success_at,
      MAX("createdAt") FILTER (WHERE success = false) AS last_failure_at,
      percentile_cont(0.95) WITHIN GROUP (ORDER BY "latencyMs")::float AS p95_ms
    FROM ai_calls
    WHERE "createdAt" >= ${since}
      AND lower(provider) = ${provider.toLowerCase()}
  `.catch(() => []);

  const r = rows[0];
  if (!r || Number(r.total) === 0) return null;

  const total = Number(r.total);
  const failed = Number(r.failed);
  return {
    lastSuccessAt: r.last_success_at?.toISOString() ?? null,
    lastFailureAt: r.last_failure_at?.toISOString() ?? null,
    errorRate24h: total > 0 ? failed / total : 0,
    latencyP95Ms: r.p95_ms != null ? Math.round(r.p95_ms) : null,
    callCount24h: total,
  };
}

async function resendMetrics(since: Date): Promise<ServiceMetrics | null> {
  // Resend sends are tracked through audit_logs (EXPORT_EMAIL_SENT
  // for success, EXPORT_EMAIL_BLOCKED_DESTINATION for client-blocked
  // attempts that still hit our send path). No per-send latency —
  // the audit-logger doesn't time its own write.
  const rows = await prisma.$queryRaw<
    {
      total: bigint;
      succeeded: bigint;
      failed: bigint;
      last_success_at: Date | null;
      last_failure_at: Date | null;
    }[]
  >`
    SELECT
      COUNT(*)::bigint AS total,
      COUNT(*) FILTER (WHERE success = true)::bigint AS succeeded,
      COUNT(*) FILTER (WHERE success = false)::bigint AS failed,
      MAX("timestamp") FILTER (WHERE success = true)  AS last_success_at,
      MAX("timestamp") FILTER (WHERE success = false) AS last_failure_at
    FROM audit_logs
    WHERE "timestamp" >= ${since}
      AND action IN ('EXPORT_EMAIL_SENT', 'EXPORT_EMAIL_BLOCKED_DESTINATION')
  `.catch(() => []);

  const r = rows[0];
  if (!r || Number(r.total) === 0) return null;

  const total = Number(r.total);
  const failed = Number(r.failed);
  return {
    lastSuccessAt: r.last_success_at?.toISOString() ?? null,
    lastFailureAt: r.last_failure_at?.toISOString() ?? null,
    errorRate24h: total > 0 ? failed / total : 0,
    latencyP95Ms: null,
    callCount24h: total,
  };
}
