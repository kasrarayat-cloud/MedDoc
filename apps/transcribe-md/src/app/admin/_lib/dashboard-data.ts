// ============================================================================
// Admin overview dashboard — server-side data layer
// ----------------------------------------------------------------------------
// Server-only helpers, called from `app/admin/page.tsx` during SSR. The
// page is `dynamic = 'force-dynamic'` so each call hits a fresh query —
// no caching surprises for an admin dashboard.
//
// We query Postgres (and ping Redis / MinIO) directly rather than calling
// our own /api/admin/* routes via fetch. The route handlers re-check
// SUPER_ADMIN via adminApi() on every hit; the layout has already done
// that gate by the time this file runs, so the extra HTTP round-trip
// would only burn latency.
//
// Each helper is best-effort: a Prisma error surfaces as a "down"
// marker or a synthetic empty result rather than throwing, so a flaky
// section never crashes the whole page.
// ============================================================================

import 'server-only';

import prisma from '@meddoc/db';
import { getRedis, isRedisReady } from '@/lib/redis';

import type {
  SystemHealth,
  ActivityRow,
  ActivityCategory,
  HealthStatus,
  Threat,
  TimelineBucket,
  PipelineMetrics,
  HipaaState,
} from '../_types';

// ---------------------------------------------------------------------------
// System health
// ---------------------------------------------------------------------------

interface PgRow {
  active: bigint;
  idle: bigint;
}

interface AiRow {
  provider: string;
  failed: bigint;
  total: bigint;
}

export async function getSystemHealth(): Promise<SystemHealth> {
  const [database, redis, minio, external] = await Promise.all([
    inspectDatabase(),
    inspectRedis(),
    inspectMinio(),
    inspectExternalApis(),
  ]);
  return { database, redis, minio, externalAPIs: external };
}

async function inspectDatabase() {
  try {
    const rows = await prisma.$queryRaw<PgRow[]>`
      SELECT
        COUNT(*) FILTER (WHERE state = 'active')::bigint AS active,
        COUNT(*) FILTER (WHERE state = 'idle')::bigint   AS idle
      FROM pg_stat_activity
      WHERE datname = current_database()
    `;
    const r = rows[0];
    if (!r) return { status: 'down' as const, metric: 'no stats' };
    const active = Number(r.active);
    const idle = Number(r.idle);
    return {
      status: 'healthy' as const,
      metric: `${active} active · ${idle} idle conns`,
    };
  } catch {
    return { status: 'down' as const, metric: 'unreachable' };
  }
}

async function inspectRedis() {
  // Two signals — singleton's own status (cheap, sync) + a PING
  // (authoritative). status === 'ready' without a successful PING would
  // be a lie, so we PING when status looks live.
  if (!isRedisReady()) {
    return { status: 'degraded' as const, metric: 'singleton not ready' };
  }
  try {
    const r = getRedis();
    const start = Date.now();
    const pong = await r.ping();
    const ms = Date.now() - start;
    if (pong !== 'PONG') {
      return { status: 'degraded' as const, metric: 'unexpected PING reply' };
    }
    const dbsize = await r.dbsize().catch(() => -1);
    return {
      status: 'healthy' as const,
      metric: `PING ${ms}ms · ${dbsize >= 0 ? `${dbsize.toLocaleString()} keys` : 'dbsize n/a'}`,
    };
  } catch {
    return { status: 'down' as const, metric: 'unreachable' };
  }
}

async function inspectMinio() {
  const endpoint = process.env.MINIO_ENDPOINT?.trim() || 'minio:9000';
  const useSsl =
    (process.env.MINIO_USE_SSL?.trim().toLowerCase() ?? 'false') === 'true';
  const url = `${useSsl ? 'https' : 'http'}://${endpoint}/minio/health/live`;
  try {
    const start = Date.now();
    const res = await fetch(url, {
      method: 'GET',
      signal: AbortSignal.timeout(2_000),
    });
    const ms = Date.now() - start;
    if (!res.ok) {
      return { status: 'degraded' as const, metric: `HTTP ${res.status} · ${ms}ms` };
    }
    return { status: 'healthy' as const, metric: `live · ${ms}ms` };
  } catch {
    return { status: 'down' as const, metric: 'unreachable' };
  }
}

async function inspectExternalApis() {
  // Aggregate ai_calls + the resend audit-log lane to determine how many
  // of the 4 providers have a non-zero error rate in the last 24h.
  // Fail-open: if the query throws, claim healthy with a warning metric
  // rather than scaring an admin during a flaky DB blip.
  try {
    const since = new Date(Date.now() - 24 * 60 * 60 * 1000);
    const rows = await prisma.$queryRaw<AiRow[]>`
      SELECT
        lower(provider)::text AS provider,
        COUNT(*) FILTER (WHERE success = false)::bigint AS failed,
        COUNT(*)::bigint AS total
      FROM ai_calls
      WHERE "createdAt" >= ${since}
      GROUP BY lower(provider)
    `;
    const knownProviders = ['deepgram', 'anthropic', 'openai'];
    let upCount = 0;
    for (const p of knownProviders) {
      const row = rows.find((r: AiRow) => r.provider === p);
      if (!row || Number(row.total) === 0) {
        upCount += 1;
      } else if (Number(row.failed) === 0) {
        upCount += 1;
      }
    }
    // Resend lane — derived from audit_logs the same way the API route does.
    const resendRows = await prisma.$queryRaw<{ failed: bigint; total: bigint }[]>`
      SELECT
        COUNT(*) FILTER (WHERE success = false)::bigint AS failed,
        COUNT(*)::bigint AS total
      FROM audit_logs
      WHERE "timestamp" >= ${since}
        AND action IN ('EXPORT_EMAIL_SENT', 'EXPORT_EMAIL_BLOCKED_DESTINATION')
    `.catch(() => []);
    const resend = resendRows[0];
    if (!resend || Number(resend.total) === 0 || Number(resend.failed) === 0) {
      upCount += 1;
    }
    const status: HealthStatus =
      upCount === 4 ? 'healthy' : upCount >= 2 ? 'degraded' : 'down';
    return { status, metric: `${upCount}/4 up` };
  } catch {
    return { status: 'degraded' as const, metric: 'metrics unreachable' };
  }
}

// ---------------------------------------------------------------------------
// Activity feed (initial page) — newest N rows, mapped to ActivityRow shape.
// SSE pushes additional rows on the client side; this is the SSR seed.
// ---------------------------------------------------------------------------

interface RawAuditRow {
  id: string;
  timestamp: Date;
  action: string;
  userEmailSnapshot: string | null;
  targetType: string | null;
  targetId: string | null;
  ipAddress: string | null;
  success: boolean | null;
}

export async function getRecentActivity(limit = 30): Promise<ActivityRow[]> {
  try {
    const rows = (await prisma.auditLog.findMany({
      orderBy: [{ timestamp: 'desc' }, { id: 'desc' }],
      take: limit,
      select: {
        id: true,
        timestamp: true,
        action: true,
        userEmailSnapshot: true,
        targetType: true,
        targetId: true,
        ipAddress: true,
        success: true,
      },
    })) as unknown as RawAuditRow[];

    return rows.map((r) => ({
      id: r.id,
      timestamp: formatClock(r.timestamp),
      action: r.action,
      category: categorizeAction(r.action),
      actorEmail: r.userEmailSnapshot ?? 'system',
      target: extractTarget(r),
      ip: r.ipAddress ?? '—',
      success: r.success ?? true,
    }));
  } catch {
    return [];
  }
}

function formatClock(d: Date): string {
  // 24h HH:MM:SS — server's local time. The dashboard caption already
  // says "last updated", so absolute clocks here are fine without a
  // timezone footer.
  const h = String(d.getHours()).padStart(2, '0');
  const m = String(d.getMinutes()).padStart(2, '0');
  const s = String(d.getSeconds()).padStart(2, '0');
  return `${h}:${m}:${s}`;
}

function categorizeAction(action: string): ActivityCategory {
  if (action.startsWith('LOGIN') || action === 'LOGOUT' || action === 'SESSION_EXPIRED') return 'auth';
  if (action.startsWith('VISIT_')) return 'visit';
  if (
    action.includes('EXPORT') ||
    action.includes('EMAIL_SENT') ||
    action.includes('EMAIL_BLOCKED') ||
    action.includes('PDF') ||
    action.includes('DOCX') ||
    action.includes('CLIPBOARD')
  )
    return 'export';
  return 'admin';
}

function extractTarget(r: { targetType: string | null; targetId: string | null }) {
  if (r.targetType && r.targetId) {
    return `${r.targetType}:${r.targetId.slice(0, 8)}`;
  }
  return undefined;
}

// ---------------------------------------------------------------------------
// Threats (last 24h) — flatten the 4 detector buckets to a single Threat[].
// Severity mapping per Phase 3 prompt:
//   failed_login_burst    → amber (5–10 attempts) / red (>10)
//   cross_tenant_attempts → red always
//   bulk_phi_access       → amber
//   export_external       → amber  (kept name parallel; the prompt called this
//                           "off_hours_access" but the actual API returns
//                           external-domain export attempts — same severity)
// ---------------------------------------------------------------------------

interface RawFailedLoginBurst {
  ipAddress: string;
  count: number;
  firstSeen: Date;
  lastSeen: Date;
  targetEmails: string[] | null;
}

interface RawCrossTenant {
  userId: string;
  attemptCount: number;
  lastSeen: Date;
}

interface RawBulkPhi {
  userId: string;
  userEmail: string | null;
  patientCount: number;
  exportCount: number;
  windowStart: Date;
  windowEnd: Date;
}

interface RawExportExternal {
  userId: string;
  externalDomain: string;
  attemptCount: number;
  lastSeen: Date;
}

const FAILED_LOGIN_BURST_THRESHOLD = 5;
const FAILED_LOGIN_BURST_WINDOW_MIN = 5;
const BULK_PHI_THRESHOLD = 50;

export async function getThreats(): Promise<Threat[]> {
  const since = new Date(Date.now() - 24 * 60 * 60 * 1000);

  const [bursts, cross, bulk, exportExt] = await Promise.all([
    prisma.$queryRaw<RawFailedLoginBurst[]>`
      WITH windowed AS (
        SELECT
          "ipAddress"::text AS ip,
          DATE_TRUNC('minute', "timestamp")
            - (EXTRACT(MINUTE FROM "timestamp")::int % ${FAILED_LOGIN_BURST_WINDOW_MIN}) * INTERVAL '1 minute'
            AS bucket_start,
          "userEmailSnapshot" AS email
        FROM audit_logs
        WHERE "timestamp" >= ${since}
          AND action = 'LOGIN_FAILED'
          AND "ipAddress" IS NOT NULL
      )
      SELECT
        ip AS "ipAddress",
        COUNT(*)::int AS count,
        MIN(bucket_start)::timestamptz AS "firstSeen",
        MAX(bucket_start)::timestamptz AS "lastSeen",
        ARRAY_AGG(DISTINCT email) FILTER (WHERE email IS NOT NULL) AS "targetEmails"
      FROM windowed
      GROUP BY ip, bucket_start
      HAVING COUNT(*) >= ${FAILED_LOGIN_BURST_THRESHOLD}
      ORDER BY "lastSeen" DESC
      LIMIT 20
    `.catch(() => [] as RawFailedLoginBurst[]),

    prisma.$queryRaw<RawCrossTenant[]>`
      SELECT
        "userId",
        COUNT(*)::int AS "attemptCount",
        MAX("timestamp")::timestamptz AS "lastSeen"
      FROM audit_logs
      WHERE "timestamp" >= ${since}
        AND success = false
        AND "errorCode" IN (
          'NO_MEDDOC_PRO_ENTITLEMENT',
          'NO_TRANSCRIBE_MD_ENTITLEMENT'
        )
        AND "userId" IS NOT NULL
      GROUP BY "userId"
      HAVING COUNT(*) >= 3
      ORDER BY "lastSeen" DESC
      LIMIT 20
    `.catch(() => [] as RawCrossTenant[]),

    prisma.$queryRaw<RawBulkPhi[]>`
      WITH bucketed AS (
        SELECT
          "userId",
          "userEmailSnapshot" AS email,
          DATE_TRUNC('hour', "timestamp") AS hour,
          COUNT(DISTINCT "targetId") FILTER (
            WHERE "targetType" IN ('TranscribeMdPatient', 'TranscribeVisit')
          )::int AS patient_count,
          COUNT(*) FILTER (
            WHERE action IN (
              'EXPORT_PDF_DOWNLOADED',
              'EXPORT_DOCX_DOWNLOADED',
              'EXPORT_CLIPBOARD_COPIED',
              'EXPORT_EMAIL_SENT'
            )
          )::int AS export_count
        FROM audit_logs
        WHERE "timestamp" >= ${since}
          AND "userId" IS NOT NULL
        GROUP BY "userId", email, hour
      )
      SELECT
        "userId",
        email AS "userEmail",
        patient_count AS "patientCount",
        export_count AS "exportCount",
        hour::timestamptz AS "windowStart",
        (hour + INTERVAL '1 hour')::timestamptz AS "windowEnd"
      FROM bucketed
      WHERE patient_count >= ${BULK_PHI_THRESHOLD}
         OR export_count >= ${BULK_PHI_THRESHOLD}
      ORDER BY "windowStart" DESC
      LIMIT 20
    `.catch(() => [] as RawBulkPhi[]),

    prisma.$queryRaw<RawExportExternal[]>`
      SELECT
        "userId",
        (metadata->>'requestedDomain')::text AS "externalDomain",
        COUNT(*)::int AS "attemptCount",
        MAX("timestamp")::timestamptz AS "lastSeen"
      FROM audit_logs
      WHERE "timestamp" >= ${since}
        AND action = 'EXPORT_EMAIL_BLOCKED_DESTINATION'
        AND "userId" IS NOT NULL
        AND metadata->>'requestedDomain' IS NOT NULL
      GROUP BY "userId", "externalDomain"
      HAVING COUNT(*) >= 1
      ORDER BY "lastSeen" DESC
      LIMIT 20
    `.catch(() => [] as RawExportExternal[]),
  ]);

  const threats: Threat[] = [];

  for (const b of bursts) {
    threats.push({
      id: `burst:${b.ipAddress}:${b.firstSeen.toISOString()}`,
      type: 'failed_login_burst',
      severity: b.count > 10 ? 'red' : 'amber',
      summary: `Failed login burst from ${b.ipAddress}`,
      detail: `${b.count} attempts in ${FAILED_LOGIN_BURST_WINDOW_MIN} min · ${
        (b.targetEmails ?? []).slice(0, 2).join(', ') || 'no email captured'
      }`,
    });
  }

  for (const c of cross) {
    threats.push({
      id: `cross:${c.userId}:${c.lastSeen.toISOString()}`,
      type: 'cross_tenant_attempts',
      severity: 'red',
      summary: `Cross-tenant access attempts by ${c.userId}`,
      detail: `${c.attemptCount} blocked attempts · last ${c.lastSeen.toISOString()}`,
    });
  }

  for (const p of bulk) {
    threats.push({
      id: `bulk:${p.userId}:${p.windowStart.toISOString()}`,
      type: 'bulk_phi_access',
      severity: 'amber',
      summary: `Bulk PHI access by ${p.userEmail ?? p.userId}`,
      detail: `${p.patientCount} patients · ${p.exportCount} exports in 1 hour`,
    });
  }

  for (const e of exportExt) {
    threats.push({
      id: `xdom:${e.userId}:${e.externalDomain}`,
      type: 'export_to_external_domain',
      severity: 'amber',
      summary: `Email export to ${e.externalDomain} blocked`,
      detail: `${e.attemptCount} attempt${e.attemptCount === 1 ? '' : 's'} by ${e.userId}`,
    });
  }

  // Sort: red first, then amber, then by detail length so the most
  // descriptive item floats to the top within each severity tier.
  threats.sort((a, b) => {
    if (a.severity !== b.severity) return a.severity === 'red' ? -1 : 1;
    return b.detail.length - a.detail.length;
  });

  return threats;
}

// ---------------------------------------------------------------------------
// Timeline — 24 hourly buckets, hour mapped to local 0-23.
// ---------------------------------------------------------------------------

interface RawBucket {
  hour: Date;
  total: bigint;
  failed: bigint;
}

const TIMELINE_HOURS = 24;

export async function getTimeline(): Promise<TimelineBucket[]> {
  try {
    const sinceFloor = new Date(Date.now() - TIMELINE_HOURS * 60 * 60 * 1000);
    sinceFloor.setMinutes(0, 0, 0);

    const rows = await prisma.$queryRaw<RawBucket[]>`
      SELECT
        date_trunc('hour', "timestamp") AS hour,
        COUNT(*)::bigint AS total,
        SUM(CASE WHEN success = false THEN 1 ELSE 0 END)::bigint AS failed
      FROM audit_logs
      WHERE "timestamp" >= ${sinceFloor}
      GROUP BY 1
      ORDER BY 1 ASC
    `;

    const byHourIso = new Map<string, { total: number; failed: number }>();
    for (const r of rows) {
      byHourIso.set(r.hour.toISOString(), {
        total: Number(r.total),
        failed: Number(r.failed),
      });
    }

    const buckets: TimelineBucket[] = [];
    for (let i = 0; i < TIMELINE_HOURS; i++) {
      const t = new Date(sinceFloor.getTime() + i * 60 * 60 * 1000);
      const hit = byHourIso.get(t.toISOString());
      buckets.push({
        hour: t.getHours(),
        total: hit?.total ?? 0,
        failed: hit?.failed ?? 0,
      });
    }
    return buckets;
  } catch {
    return Array.from({ length: TIMELINE_HOURS }, (_, h) => ({
      hour: h,
      total: 0,
      failed: 0,
    }));
  }
}

// ---------------------------------------------------------------------------
// Pipeline metrics (last 24h). Pending = QUEUED visits (not in the API
// response); we add it here so the stacked-bar visualisation tells the
// honest "in-flight" story.
// ---------------------------------------------------------------------------

interface RawPipelineRow {
  total: bigint;
  succeeded: bigint;
  failed: bigint;
  p50_ms: number | null;
  p95_ms: number | null;
}

export async function getPipelineMetrics(): Promise<PipelineMetrics> {
  const since = new Date(Date.now() - 24 * 60 * 60 * 1000);

  try {
    const [main, pendingRows] = await Promise.all([
      prisma.$queryRaw<RawPipelineRow[]>`
        SELECT
          COUNT(*)::bigint AS total,
          COUNT(*) FILTER (WHERE status IN ('READY', 'SIGNED'))::bigint AS succeeded,
          COUNT(*) FILTER (WHERE status = 'FAILED')::bigint AS failed,
          percentile_cont(0.50) WITHIN GROUP (
            ORDER BY EXTRACT(EPOCH FROM ("processingFinishedAt" - "processingStartedAt")) * 1000
          )::float AS p50_ms,
          percentile_cont(0.95) WITHIN GROUP (
            ORDER BY EXTRACT(EPOCH FROM ("processingFinishedAt" - "processingStartedAt")) * 1000
          )::float AS p95_ms
        FROM transcribe_visits
        WHERE "processingFinishedAt" >= ${since}
          AND "processingStartedAt" IS NOT NULL
      `,
      prisma.$queryRaw<{ pending: bigint }[]>`
        SELECT COUNT(*)::bigint AS pending
        FROM transcribe_visits
        WHERE status = 'QUEUED'
      `,
    ]);

    const m = main[0];
    const p = pendingRows[0];
    const total = Number(m?.total ?? 0);
    const succeeded = Number(m?.succeeded ?? 0);
    const failed = Number(m?.failed ?? 0);
    const pending = Number(p?.pending ?? 0);
    const successRate = total > 0 ? (succeeded / total) * 100 : 0;

    return {
      total: total + pending,
      succeeded,
      failed,
      pending,
      successRate,
      p50: m?.p50_ms != null ? formatLatency(m.p50_ms) : '—',
      p95: m?.p95_ms != null ? formatLatency(m.p95_ms) : '—',
    };
  } catch {
    return {
      total: 0,
      succeeded: 0,
      failed: 0,
      pending: 0,
      successRate: 0,
      p50: '—',
      p95: '—',
    };
  }
}

function formatLatency(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

// ---------------------------------------------------------------------------
// HIPAA state — placeholder until a real findings endpoint exists. The
// numbers come from the AUDIT-COVERAGE doc and the most recent ultra-final
// audit; a real API replaces this in a later phase.
// ---------------------------------------------------------------------------

export async function getHipaaState(): Promise<HipaaState> {
  return {
    findings: [
      { severity: 'critical', total: 0, resolved: 0 },
      { severity: 'high', total: 4, resolved: 1 },
      { severity: 'medium', total: 0, resolved: 0 },
    ],
    auditCoverage: { covered: 26, total: 26 },
    lastReview: 'today',
  };
}
