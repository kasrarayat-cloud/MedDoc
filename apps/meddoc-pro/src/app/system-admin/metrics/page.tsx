// ============================================================================
// System Admin — Metrics
// ----------------------------------------------------------------------------
// System-wide health snapshot. Counts come from Prisma when the DB is healthy;
// otherwise the page falls back to indicative mock values so the surface stays
// usable during local dev with no database. ADMIN-only access is enforced by
// the /system-admin layout.
//
// API latency is intentionally mocked — we don't yet have a probe pipeline.
// Cost estimates are computed at read time using published OpenAI rates
// (see calculateEstimatedCost). Stored per-row are the INPUTS (tokens,
// durationSeconds) — not the cost — so rate changes don't need backfills.
// ============================================================================

import prisma, { isDatabaseHealthy } from '@meddoc/db';
import { getSession, type Session } from '@/lib/auth';
import { tenantScope } from '@/lib/tenancy';
import MetricsDashboard, {
  type FeatureCostRow,
  type MetricsSnapshot,
  type TopConsumer,
} from './MetricsDashboard';

export const dynamic = 'force-dynamic';

// ----------------------------------------------------------------------------
// Pricing table (source: https://openai.com/api/pricing/, checked 2026-04)
// ----------------------------------------------------------------------------
// Each entry says how to price a feature. `minutes` = use durationSeconds,
// `tokens` = use tokens column, `chars` = use tokens column as char-count
// (TTS stores text.length there). Unknown features fall through as $0
// with a console warning so we notice if a new feature lands without a
// pricing row.
//
// Rates are intentionally approximations — the goal is "within 20% of the
// OpenAI bill", not exact penny-matching. Blended rates used where OpenAI
// prices input/output separately (we don't track that split yet).
type PricingRule =
  | { kind: 'minutes'; usdPerMinute: number }
  | { kind: 'tokens'; usdPer1K: number }
  | { kind: 'chars'; usdPer1K: number };

const PRICING: Record<string, PricingRule> = {
  TRANSCRIBE: { kind: 'minutes', usdPerMinute: 0.006 }, // Whisper
  DOC_EDITOR: { kind: 'tokens', usdPer1K: 0.01 },       // rough for gpt-4o-mini I/O mix
  TTS: { kind: 'chars', usdPer1K: 0.015 },              // gpt-4o-mini-tts, per-char
  // Realtime voice is the biggest ticket. Blended input+output ≈ $0.15/min.
  REALTIME_VOICE: { kind: 'minutes', usdPerMinute: 0.15 },
  // Per-tool GPT calls (SOAP format, edit rewrite, summary, doc draft, etc.).
  // gpt-4o-mini blended input+output ≈ $0.00045/1K tokens — round to .001.
  GPT_TOOL: { kind: 'tokens', usdPer1K: 0.001 },
};

export function calculateEstimatedCost(
  feature: string,
  totals: { tokens?: number | null; durationSeconds?: number | null },
  count: number
): number {
  const rule = PRICING[feature];
  if (!rule) {
    // Unknown feature — log once per cold start so new features don't
    // silently drop to $0.
    console.warn(`[metrics] no pricing rule for feature="${feature}"; contributing $0`);
    return 0;
  }
  if (rule.kind === 'minutes') {
    const seconds = totals.durationSeconds ?? 0;
    if (seconds > 0) return (seconds / 60) * rule.usdPerMinute;
    // Fallback for duration-priced features where duration wasn't captured:
    // assume 1 minute per hit. Better than $0; keeps the number directional.
    return count * rule.usdPerMinute;
  }
  // tokens + chars both price off the tokens column.
  const units = totals.tokens ?? 0;
  return (units / 1000) * rule.usdPer1K;
}

const MOCK_TOP_CONSUMERS: TopConsumer[] = (() => {
  const mkRow = (userId: string, email: string, name: string, count: number, avgSec: number) => ({
    userId,
    email,
    name,
    count,
    tokens: null,
    durationSeconds: count * avgSec,
    costUsd: calculateEstimatedCost(
      'TRANSCRIBE',
      { durationSeconds: count * avgSec },
      count
    ),
  });
  return [
    mkRow('mock-1', 'dr.mitchell@clinic.dev', 'Sarah Mitchell', 42, 58),
    mkRow('mock-2', 'dr.patel@clinic.dev', 'Ravi Patel', 31, 65),
    mkRow('mock-3', 'dr.okafor@clinic.dev', 'Ada Okafor', 24, 52),
    mkRow('mock-4', 'intake@clinic.dev', 'Front Desk', 11, 48),
  ];
})();

async function getTopConsumers(
  session: Session,
  since: Date
): Promise<TopConsumer[]> {
  try {
    // Transcription-only leaderboard per current spec. Scoped to the
    // session's practice unless SUPER_ADMIN.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const grouped: any[] = await prisma.apiUsage.groupBy({
      by: ['userId'],
      where: {
        createdAt: { gte: since },
        feature: 'TRANSCRIBE',
        ...tenantScope(session),
      },
      _count: { _all: true },
      _sum: { tokens: true, durationSeconds: true },
      orderBy: { _count: { userId: 'desc' } },
      take: 10,
    });

    if (grouped.length === 0) return [];

    const userIds = grouped.map((g) => g.userId);
    const users = await prisma.user.findMany({
      where: { id: { in: userIds } },
      select: { id: true, email: true, name: true },
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const byId = new Map<string, any>(users.map((u: any) => [u.id, u]));

    return grouped.map((g) => {
      const u = byId.get(g.userId);
      const count = g._count?._all ?? 0;
      const tokens = g._sum?.tokens ?? null;
      const durationSeconds = g._sum?.durationSeconds ?? null;
      return {
        userId: g.userId,
        email: u?.email ?? 'unknown',
        name: u?.name ?? null,
        count,
        tokens,
        durationSeconds,
        costUsd: calculateEstimatedCost('TRANSCRIBE', { tokens, durationSeconds }, count),
      };
    });
  } catch (err) {
    console.warn('[system-admin/metrics] Top consumers query failed:', err);
    return [];
  }
}

async function getFeatureBreakdown24h(
  session: Session,
  since: Date
): Promise<{ total: number; breakdown: FeatureCostRow[] }> {
  try {
    // One groupBy query across ALL features. No hardcoded feature names —
    // anything in apiUsage gets picked up, priced per PRICING, and surfaced.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const grouped: any[] = await prisma.apiUsage.groupBy({
      by: ['feature'],
      where: { createdAt: { gte: since }, ...tenantScope(session) },
      _count: { _all: true },
      _sum: { tokens: true, durationSeconds: true },
    });

    const breakdown: FeatureCostRow[] = grouped.map((g) => {
      const feature = g.feature ?? 'UNKNOWN';
      const count = g._count?._all ?? 0;
      const tokens = g._sum?.tokens ?? null;
      const durationSeconds = g._sum?.durationSeconds ?? null;
      const costUsd = calculateEstimatedCost(
        feature,
        { tokens, durationSeconds },
        count
      );
      return { feature, count, tokens, durationSeconds, costUsd };
    });
    breakdown.sort((a, b) => b.costUsd - a.costUsd);
    const total = breakdown.reduce((sum, r) => sum + r.costUsd, 0);
    return { total, breakdown };
  } catch (err) {
    console.warn('[system-admin/metrics] Feature breakdown query failed:', err);
    return { total: 0, breakdown: [] };
  }
}

async function getMetrics(session: Session): Promise<MetricsSnapshot> {
  const endpoints = [
    { path: '/api/transcribe', p50: 142, p95: 318, status: 'healthy' as const },
    { path: '/api/doc-editor', p50: 88, p95: 212, status: 'healthy' as const },
    { path: '/api/doc-editor/save', p50: 54, p95: 134, status: 'healthy' as const },
    { path: '/api/auth/[...nextauth]', p50: 38, p95: 96, status: 'healthy' as const },
  ];

  if (!(await isDatabaseHealthy())) {
    const mockCost = MOCK_TOP_CONSUMERS.reduce((a, c) => a + c.costUsd, 0);
    return {
      totalUsers: 12,
      activeUsers: 9,
      adminUsers: 2,
      activeSessions: 4,
      sessions24h: 37,
      auditEvents24h: 184,
      failedLogins24h: 3,
      apiCalls24h: 108,
      estimatedCost24hUsd: mockCost,
      featureBreakdown: [
        { feature: 'REALTIME_VOICE', count: 14, tokens: null, durationSeconds: 2100, costUsd: (2100 / 60) * 0.15 },
        { feature: 'TRANSCRIBE', count: 108, tokens: null, durationSeconds: 6200, costUsd: (6200 / 60) * 0.006 },
      ],
      topConsumers: MOCK_TOP_CONSUMERS,
      endpoints,
      dbHealthy: false,
    };
  }

  const since24h = new Date(Date.now() - 24 * 60 * 60 * 1000);
  // "Active" sessions — treat any login event in the last 30 min as active,
  // since we don't track session close events in SessionLog.
  const activeWindow = new Date(Date.now() - 30 * 60 * 1000);

  // Every query below is tenant-scoped unless the caller is SUPER_ADMIN.
  const scope = tenantScope(session);

  try {
    const [
      totalUsers,
      activeUsers,
      adminUsers,
      activeSessions,
      sessions24h,
      auditEvents24h,
      failedLogins24h,
      apiCalls24h,
      topConsumers,
      costBreakdown,
    ] = await Promise.all([
      prisma.user.count({ where: { ...scope } }),
      prisma.user.count({ where: { ...scope, isActive: true } }),
      prisma.user.count({ where: { ...scope, role: 'ADMIN' } }),
      prisma.sessionLog.count({
        where: { ...scope, createdAt: { gte: activeWindow } },
      }),
      prisma.sessionLog.count({
        where: { ...scope, createdAt: { gte: since24h } },
      }),
      prisma.auditLog.count({
        where: { ...scope, timestamp: { gte: since24h } },
      }),
      prisma.auditLog.count({
        where: {
          ...scope,
          timestamp: { gte: since24h },
          action: 'LOGIN_FAILED',
        },
      }),
      prisma.apiUsage.count({
        where: { ...scope, createdAt: { gte: since24h } },
      }),
      getTopConsumers(session, since24h),
      getFeatureBreakdown24h(session, since24h),
    ]);

    return {
      totalUsers,
      activeUsers,
      adminUsers,
      activeSessions,
      sessions24h,
      auditEvents24h,
      failedLogins24h,
      apiCalls24h,
      estimatedCost24hUsd: costBreakdown.total,
      featureBreakdown: costBreakdown.breakdown,
      topConsumers,
      endpoints,
      dbHealthy: true,
    };
  } catch (err) {
    console.warn('[system-admin/metrics] Prisma query failed:', err);
    return {
      totalUsers: 0,
      activeUsers: 0,
      adminUsers: 0,
      activeSessions: 0,
      sessions24h: 0,
      auditEvents24h: 0,
      failedLogins24h: 0,
      apiCalls24h: 0,
      estimatedCost24hUsd: 0,
      featureBreakdown: [],
      topConsumers: [],
      endpoints,
      dbHealthy: false,
    };
  }
}

export default async function SystemAdminMetricsPage() {
  const session = await getSession();
  if (!session) return null; // layout gate already guarantees this
  const snapshot = await getMetrics(session);
  return <MetricsDashboard snapshot={snapshot} />;
}
