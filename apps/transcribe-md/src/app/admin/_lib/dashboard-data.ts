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
import { resolveAuditWindow } from '../../api/admin/_audit-window';

import type {
  SystemHealth,
  ActivityRow,
  ActivityCategory,
  HealthStatus,
  Threat,
  ResolvedThreat,
  ThreatResolutionKind,
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


/** Detector queries must not take the whole security dashboard down — but a
 *  detector that silently returns [] is INDISTINGUISHABLE from "no threats
 *  found". That is exactly how the PHI-export volume-spike detector stayed
 *  dead in production for 90 days: `action LIKE 'EXPORT_%'` against a Postgres
 *  enum throws 42883, and a bare `.catch(() => [])` rendered that as a clean
 *  "no threats". Prod Postgres logs carried 965 occurrences of the error while
 *  /admin/security reported all-clear.
 *
 *  Failing soft stays correct — one broken detector must not blank the page —
 *  but it has to be LOUD, so a dead detector appears in the log stream instead
 *  of masquerading as a clean bill of health. */
function detectorFail<T>(detector: string): (err: unknown) => T[] {
  return (err: unknown) => {
    console.error(
      `[admin:threat-detector] ${detector} FAILED — this detector is BLIND, not clean:`,
      err instanceof Error ? err.message : String(err)
    );
    return [] as T[];
  };
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
    `.catch(detectorFail<{ failed: bigint; total: bigint }>('resend-health-lane'));
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

interface RawPrivilegeEsc {
  id: string;
  timestamp: Date;
  actorEmail: string | null;
  targetEmail: string | null;
  targetId: string | null;
}

interface RawVolumeSpike {
  userId: string;
  userEmail: string | null;
  today: number;
  baseline: number;
  multiple: number;
  day: Date;
}

const FAILED_LOGIN_BURST_THRESHOLD = 5;
const FAILED_LOGIN_BURST_WINDOW_MIN = 5;
const BULK_PHI_THRESHOLD = 50;
/** Privilege-escalation detector window. 7 days matches the prompt
 *  spec — long enough that a sudden grant gets reviewed, short enough
 *  that the panel doesn't permanently carry historical noise. */
const PRIVILEGE_ESCALATION_WINDOW_DAYS = 7;

// Phase 8 — Detector 4: PHI export volume spike. Closes
// hipaa_findings.h7b-detector4 (Phase 6Z-09 follow-up).
//   Baseline: per-user mean export count per calendar day over the
//   prior 14 days, requiring at least 7 days of history (so we don't
//   flag a brand-new doctor on day 2).
//   Trigger:  today's count >= 3x baseline AND today's count >= 5
//             absolute (so a baseline of 0.3 doesn't pop on a single
//             export).
//   Severity: amber when multiple is 3..10x; red when >10x — mirrors
//             the failed-login-burst severity ladder so a serious
//             exfiltration sorts above noisier amber items.
const VOLUME_SPIKE_HISTORY_DAYS = 14;
const VOLUME_SPIKE_MIN_HISTORY_DAYS = 7;
const VOLUME_SPIKE_MULTIPLE_THRESHOLD = 3;
const VOLUME_SPIKE_RED_MULTIPLE = 10;
const VOLUME_SPIKE_MIN_TODAY = 5;

/**
 * Phase 6H — silence-pattern matcher.
 *
 * A `ThreatResolution` row may carry a `silencePattern` JSON object that
 * tells future detector runs to suppress similar threats (e.g. "always
 * dismiss exports to test-pattern.invalid"). We re-derive each candidate
 * threat's identifying tuple here and check it against every stored
 * pattern.
 *
 * The supported pattern keys per threat type match what the detector
 * SQL above produces — keeping them parallel makes the matcher trivial:
 *
 *   failed_login_burst        { type, ipAddress }
 *   cross_tenant_attempts     { type, userId }
 *   bulk_phi_access           { type, userId }
 *   export_to_external_domain { type, userId?, domain? }   (either or both)
 *   privilege_escalation      { type }                     (silences ALL grants — rarely useful)
 *
 * `type` is required on every pattern; a pattern without it would be a
 * footgun (would silence everything).
 */
function matchesSilencePattern(
  threat: Threat,
  pattern: Record<string, unknown>
): boolean {
  if (typeof pattern.type !== 'string' || pattern.type !== threat.type) {
    return false;
  }
  // Decode the threat's ID back into its identifying parts. IDs are
  // built up in the loops below as `<kind>:<part1>:<part2>`.
  const parts = threat.id.split(':');
  // Phase 6Z hardening: every type-specific case requires its
  // identifying subkey to be present on the pattern. Without this,
  // a pattern like { type: 'failed_login_burst' } (no ipAddress) would
  // silence EVERY future failed-login burst — a footgun for an admin
  // who hand-crafts a silencePattern via the dismiss API. The xdom
  // case already had this guard; mirroring it everywhere now.
  switch (threat.type) {
    case 'failed_login_burst': {
      // burst:<ip>:<isoTimestamp>
      if (pattern.ipAddress == null) return false;
      const ip = parts[1];
      return pattern.ipAddress === ip;
    }
    case 'cross_tenant_attempts': {
      // cross:<userId>:<isoTimestamp>
      if (pattern.userId == null) return false;
      const userId = parts[1];
      return pattern.userId === userId;
    }
    case 'bulk_phi_access': {
      // bulk:<userId>:<isoTimestamp>
      if (pattern.userId == null) return false;
      const userId = parts[1];
      return pattern.userId === userId;
    }
    case 'export_to_external_domain': {
      // xdom:<userId>:<domain>
      // At least one of userId/domain must be specified — otherwise the
      // pattern would silence all xdom threats globally.
      if (pattern.userId == null && pattern.domain == null) return false;
      const userId = parts[1];
      const domain = parts.slice(2).join(':');
      const userOk = pattern.userId == null || pattern.userId === userId;
      const domainOk = pattern.domain == null || pattern.domain === domain;
      return userOk && domainOk;
    }
    case 'privilege_escalation':
      // No useful sub-key; we just rely on per-row exact-id resolution.
      return false;
    case 'volume_spike': {
      // volume-spike:<userId>:<YYYY-MM-DD>
      // Phase 8: silence per-user (rare — covers "this user has a
      // legitimately high baseline"); silencing all volume spikes
      // platform-wide is the kind of footgun the per-type guard
      // exists to prevent.
      if (pattern.userId == null) return false;
      const userId = parts[1];
      return pattern.userId === userId;
    }
    default:
      return false;
  }
}

interface ResolutionRow {
  threatId: string;
  resolutionKind: string;
  silencePattern: unknown;
}

/** Phase 6Z (PHASE-6Z-11): bound the resolution scan to the last 90 days.
 *  Pre-launch scale doesn't strictly need this (3 rows today; even 10K
 *  is fine in-memory), but it costs nothing and keeps the Overview SSR
 *  cheap as the table grows. The detector windows are 24h or 7d, so a
 *  90d resolution row covers every still-relevant detector hit by a
 *  comfortable margin. Older resolutions remain in the table for the
 *  audit trail; they just stop being applied as live filters. */
const RESOLUTION_LOOKBACK_DAYS = 90;
async function loadActiveResolutions(): Promise<{
  byThreatId: Set<string>;
  silencePatterns: Record<string, unknown>[];
}> {
  try {
    const since = new Date(
      Date.now() - RESOLUTION_LOOKBACK_DAYS * 24 * 60 * 60 * 1000
    );
    const rows = (await prisma.threatResolution.findMany({
      where: { resolvedAt: { gte: since } },
      select: { threatId: true, resolutionKind: true, silencePattern: true },
    })) as unknown as ResolutionRow[];
    const byThreatId = new Set<string>();
    const silencePatterns: Record<string, unknown>[] = [];
    for (const r of rows) {
      byThreatId.add(r.threatId);
      if (
        r.silencePattern &&
        typeof r.silencePattern === 'object' &&
        !Array.isArray(r.silencePattern)
      ) {
        silencePatterns.push(r.silencePattern as Record<string, unknown>);
      }
    }
    return { byThreatId, silencePatterns };
  } catch {
    return { byThreatId: new Set(), silencePatterns: [] };
  }
}

export async function getThreats(): Promise<Threat[]> {
  const since = new Date(Date.now() - 24 * 60 * 60 * 1000);
  const sincePriv = new Date(
    Date.now() - PRIVILEGE_ESCALATION_WINDOW_DAYS * 24 * 60 * 60 * 1000
  );

  const [bursts, cross, bulk, exportExt, privEsc, volumeSpikes, resolutions] = await Promise.all([
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
    `.catch(detectorFail<RawFailedLoginBurst>('RawFailedLoginBurst')),

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
    `.catch(detectorFail<RawCrossTenant>('RawCrossTenant')),

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
    `.catch(detectorFail<RawBulkPhi>('RawBulkPhi')),

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
    `.catch(detectorFail<RawExportExternal>('RawExportExternal')),

    // Phase 6G — Detector 3: privilege escalation. Each
    // USER_GRANTED_SUPER_ADMIN row in the last 7 days is its own threat
    // (no aggregation — granting admin is rare enough that every
    // instance deserves an explicit "is this still expected?" review).
    prisma.$queryRaw<RawPrivilegeEsc[]>`
      SELECT
        id,
        timestamp,
        "userEmailSnapshot" AS "actorEmail",
        (metadata->>'targetEmail')::text AS "targetEmail",
        "targetId"
      FROM audit_logs
      WHERE "timestamp" >= ${sincePriv}
        AND action = 'USER_GRANTED_SUPER_ADMIN'
      ORDER BY "timestamp" DESC
      LIMIT 20
    `.catch(detectorFail<RawPrivilegeEsc>('RawPrivilegeEsc')),

    // Phase 8 — Detector 4: PHI export volume spike. CTE pattern:
    //   per_day  : count of EXPORT_* per (userId, day) over last 14d
    //   baseline : per-user mean of those daily counts EXCLUDING today,
    //              gated on >=7 days of history so brand-new doctors
    //              don't get flagged on day-2.
    //   today    : same per-day count for today.
    // Trigger when today >= 3x baseline AND today >= 5 absolute.
    prisma.$queryRaw<RawVolumeSpike[]>`
      WITH per_day AS (
        SELECT
          "userId",
          DATE_TRUNC('day', "timestamp") AS day,
          COUNT(*)::int AS exports
        FROM audit_logs
        WHERE "timestamp" >= NOW() - (${VOLUME_SPIKE_HISTORY_DAYS} || ' days')::interval
          AND action::text LIKE 'EXPORT_%'
          AND "userId" IS NOT NULL
        GROUP BY "userId", day
      ),
      baseline AS (
        SELECT
          "userId",
          AVG(exports)::float AS avg_per_day
        FROM per_day
        WHERE day < DATE_TRUNC('day', NOW())
        GROUP BY "userId"
        HAVING COUNT(*) >= ${VOLUME_SPIKE_MIN_HISTORY_DAYS}
      ),
      today AS (
        SELECT "userId", exports AS today_count
        FROM per_day
        WHERE day = DATE_TRUNC('day', NOW())
      )
      SELECT
        t."userId",
        u.email AS "userEmail",
        t.today_count::int AS today,
        b.avg_per_day::float AS baseline,
        (t.today_count::float / NULLIF(b.avg_per_day, 0))::float AS multiple,
        DATE_TRUNC('day', NOW()) AS day
      FROM today t
      JOIN baseline b ON b."userId" = t."userId"
      LEFT JOIN users u ON u.id = t."userId"
      WHERE t.today_count >= b.avg_per_day * ${VOLUME_SPIKE_MULTIPLE_THRESHOLD}
        AND t.today_count >= ${VOLUME_SPIKE_MIN_TODAY}
      ORDER BY multiple DESC
      LIMIT 20
    `.catch(detectorFail<RawVolumeSpike>('RawVolumeSpike')),

    loadActiveResolutions(),
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

  for (const p of privEsc) {
    const target = p.targetEmail ?? p.targetId ?? 'unknown user';
    const actor = p.actorEmail ?? 'unknown actor';
    threats.push({
      id: `grant-admin:${p.id}`,
      type: 'privilege_escalation',
      // Privilege grants are review-worthy but not active attacks —
      // amber by default. A real compromise would also produce
      // failed-login bursts (red) which sort to the top.
      severity: 'amber',
      summary: `Admin privileges granted to ${target}`,
      detail: `By ${actor} · ${p.timestamp.toISOString().slice(0, 10)}`,
    });
  }

  for (const v of volumeSpikes) {
    // Stable id per spec: volume-spike:<userId>:<YYYY-MM-DD>. The day
    // suffix means a fresh threat appears each day the spike repeats
    // — admins resolve today's, then tomorrow's reappears if the
    // anomaly continues.
    const dayKey = v.day.toISOString().slice(0, 10);
    const who = v.userEmail ?? v.userId;
    const mult = Number(v.multiple ?? 0);
    threats.push({
      id: `volume-spike:${v.userId}:${dayKey}`,
      type: 'volume_spike',
      severity: mult > VOLUME_SPIKE_RED_MULTIPLE ? 'red' : 'amber',
      summary: `Export volume spike — ${who}`,
      detail: `${v.today} exports today (${mult.toFixed(1)}x baseline of ${v.baseline.toFixed(1)}/day)`,
    });
  }

  // Phase 6H — drop anything an admin already resolved or dismissed,
  // then drop anything that matches a stored silencePattern.
  const filtered = threats.filter((t) => {
    if (resolutions.byThreatId.has(t.id)) return false;
    for (const p of resolutions.silencePatterns) {
      if (matchesSilencePattern(t, p)) return false;
    }
    return true;
  });

  // Sort: red first, then amber, then by detail length so the most
  // descriptive item floats to the top within each severity tier.
  filtered.sort((a, b) => {
    if (a.severity !== b.severity) return a.severity === 'red' ? -1 : 1;
    return b.detail.length - a.detail.length;
  });

  return filtered;
}

// ---------------------------------------------------------------------------
// Phase 6H — resolved-threats history. Re-derives the active threat list
// for the requested window then keeps only those an admin acted on,
// stitching in resolution metadata so the UI can render the audit trail.
//
// Why the re-derivation? Detector queries are cheap (every WHERE is on
// an indexed timestamp) and this keeps the source of truth in one
// place — we don't need a parallel "historical threat" table.
// ---------------------------------------------------------------------------

interface ResolvedRow {
  threatId: string;
  resolutionKind: ThreatResolutionKind;
  resolvedAt: Date;
  resolvedByEmail: string | null;
  note: string | null;
}

export async function getResolvedThreats(
  window: '7d' | '30d' = '7d'
): Promise<ResolvedThreat[]> {
  const days = window === '30d' ? 30 : 7;
  const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000);

  // Pull resolution rows up front — they bound everything else.
  let resolutions: ResolvedRow[];
  try {
    resolutions = (await prisma.threatResolution.findMany({
      where: { resolvedAt: { gte: since } },
      orderBy: { resolvedAt: 'desc' },
      select: {
        threatId: true,
        resolutionKind: true,
        resolvedAt: true,
        resolvedByEmail: true,
        note: true,
      },
    })) as unknown as ResolvedRow[];
  } catch {
    return [];
  }
  if (resolutions.length === 0) return [];

  // Re-derive the *active threat universe* for the same window, then
  // join. Detectors run with their own per-type lookbacks (24h or 7d);
  // for the history view we widen those windows so old resolutions can
  // still find their source row.
  const sinceDetect = new Date(Date.now() - days * 24 * 60 * 60 * 1000);

  const [bursts, cross, bulk, exportExt, privEsc, volumeSpikes] = await Promise.all([
    prisma.$queryRaw<RawFailedLoginBurst[]>`
      WITH windowed AS (
        SELECT
          "ipAddress"::text AS ip,
          DATE_TRUNC('minute', "timestamp")
            - (EXTRACT(MINUTE FROM "timestamp")::int % ${FAILED_LOGIN_BURST_WINDOW_MIN}) * INTERVAL '1 minute'
            AS bucket_start,
          "userEmailSnapshot" AS email
        FROM audit_logs
        WHERE "timestamp" >= ${sinceDetect}
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
    `.catch(detectorFail<RawFailedLoginBurst>('RawFailedLoginBurst')),

    prisma.$queryRaw<RawCrossTenant[]>`
      SELECT
        "userId",
        COUNT(*)::int AS "attemptCount",
        MAX("timestamp")::timestamptz AS "lastSeen"
      FROM audit_logs
      WHERE "timestamp" >= ${sinceDetect}
        AND success = false
        AND "errorCode" IN (
          'NO_MEDDOC_PRO_ENTITLEMENT',
          'NO_TRANSCRIBE_MD_ENTITLEMENT'
        )
        AND "userId" IS NOT NULL
      GROUP BY "userId"
      HAVING COUNT(*) >= 3
    `.catch(detectorFail<RawCrossTenant>('RawCrossTenant')),

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
        WHERE "timestamp" >= ${sinceDetect}
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
    `.catch(detectorFail<RawBulkPhi>('RawBulkPhi')),

    prisma.$queryRaw<RawExportExternal[]>`
      SELECT
        "userId",
        (metadata->>'requestedDomain')::text AS "externalDomain",
        COUNT(*)::int AS "attemptCount",
        MAX("timestamp")::timestamptz AS "lastSeen"
      FROM audit_logs
      WHERE "timestamp" >= ${sinceDetect}
        AND action = 'EXPORT_EMAIL_BLOCKED_DESTINATION'
        AND "userId" IS NOT NULL
        AND metadata->>'requestedDomain' IS NOT NULL
      GROUP BY "userId", "externalDomain"
      HAVING COUNT(*) >= 1
    `.catch(detectorFail<RawExportExternal>('RawExportExternal')),

    prisma.$queryRaw<RawPrivilegeEsc[]>`
      SELECT
        id,
        timestamp,
        "userEmailSnapshot" AS "actorEmail",
        (metadata->>'targetEmail')::text AS "targetEmail",
        "targetId"
      FROM audit_logs
      WHERE "timestamp" >= ${sinceDetect}
        AND action = 'USER_GRANTED_SUPER_ADMIN'
    `.catch(detectorFail<RawPrivilegeEsc>('RawPrivilegeEsc')),

    // Phase 8 — Detector 4 mirror in the historical view. Same CTE
    // shape as the live getThreats() detector; widening to the history
    // window means a resolved volume_spike threat from N days ago can
    // still find its source row when re-derived.
    prisma.$queryRaw<RawVolumeSpike[]>`
      WITH per_day AS (
        SELECT
          "userId",
          DATE_TRUNC('day', "timestamp") AS day,
          COUNT(*)::int AS exports
        FROM audit_logs
        WHERE "timestamp" >= ${sinceDetect}
          AND action::text LIKE 'EXPORT_%'
          AND "userId" IS NOT NULL
        GROUP BY "userId", day
      ),
      baseline AS (
        SELECT
          "userId",
          AVG(exports)::float AS avg_per_day
        FROM per_day
        GROUP BY "userId"
        HAVING COUNT(*) >= ${VOLUME_SPIKE_MIN_HISTORY_DAYS}
      )
      SELECT
        p."userId",
        u.email AS "userEmail",
        p.exports AS today,
        b.avg_per_day AS baseline,
        (p.exports::float / NULLIF(b.avg_per_day, 0))::float AS multiple,
        p.day AS day
      FROM per_day p
      JOIN baseline b ON b."userId" = p."userId"
      LEFT JOIN users u ON u.id = p."userId"
      WHERE p.exports >= b.avg_per_day * ${VOLUME_SPIKE_MULTIPLE_THRESHOLD}
        AND p.exports >= ${VOLUME_SPIKE_MIN_TODAY}
    `.catch(detectorFail<RawVolumeSpike>('RawVolumeSpike')),
  ]);

  // Index every potential threat by its deterministic id so we can
  // look them up by the resolution.threatId join key.
  const byId = new Map<string, Threat>();

  for (const b of bursts) {
    const t: Threat = {
      id: `burst:${b.ipAddress}:${b.firstSeen.toISOString()}`,
      type: 'failed_login_burst',
      severity: b.count > 10 ? 'red' : 'amber',
      summary: `Failed login burst from ${b.ipAddress}`,
      detail: `${b.count} attempts in ${FAILED_LOGIN_BURST_WINDOW_MIN} min · ${
        (b.targetEmails ?? []).slice(0, 2).join(', ') || 'no email captured'
      }`,
    };
    byId.set(t.id, t);
  }
  for (const c of cross) {
    const t: Threat = {
      id: `cross:${c.userId}:${c.lastSeen.toISOString()}`,
      type: 'cross_tenant_attempts',
      severity: 'red',
      summary: `Cross-tenant access attempts by ${c.userId}`,
      detail: `${c.attemptCount} blocked attempts · last ${c.lastSeen.toISOString()}`,
    };
    byId.set(t.id, t);
  }
  for (const p of bulk) {
    const t: Threat = {
      id: `bulk:${p.userId}:${p.windowStart.toISOString()}`,
      type: 'bulk_phi_access',
      severity: 'amber',
      summary: `Bulk PHI access by ${p.userEmail ?? p.userId}`,
      detail: `${p.patientCount} patients · ${p.exportCount} exports in 1 hour`,
    };
    byId.set(t.id, t);
  }
  for (const e of exportExt) {
    const t: Threat = {
      id: `xdom:${e.userId}:${e.externalDomain}`,
      type: 'export_to_external_domain',
      severity: 'amber',
      summary: `Email export to ${e.externalDomain} blocked`,
      detail: `${e.attemptCount} attempt${e.attemptCount === 1 ? '' : 's'} by ${e.userId}`,
    };
    byId.set(t.id, t);
  }
  for (const p of privEsc) {
    const target = p.targetEmail ?? p.targetId ?? 'unknown user';
    const actor = p.actorEmail ?? 'unknown actor';
    const t: Threat = {
      id: `grant-admin:${p.id}`,
      type: 'privilege_escalation',
      severity: 'amber',
      summary: `Admin privileges granted to ${target}`,
      detail: `By ${actor} · ${p.timestamp.toISOString().slice(0, 10)}`,
    };
    byId.set(t.id, t);
  }
  for (const v of volumeSpikes) {
    const dayKey = v.day.toISOString().slice(0, 10);
    const who = v.userEmail ?? v.userId;
    const mult = Number(v.multiple ?? 0);
    const t: Threat = {
      id: `volume-spike:${v.userId}:${dayKey}`,
      type: 'volume_spike',
      severity: mult > VOLUME_SPIKE_RED_MULTIPLE ? 'red' : 'amber',
      summary: `Export volume spike — ${who}`,
      detail: `${v.today} exports today (${mult.toFixed(1)}x baseline of ${v.baseline.toFixed(1)}/day)`,
    };
    byId.set(t.id, t);
  }

  // Stitch resolution metadata onto each matching threat. If the source
  // audit row has aged out of the detector window we still surface a
  // skeletal entry so the resolution itself isn't invisible.
  const out: ResolvedThreat[] = [];
  for (const r of resolutions) {
    const base = byId.get(r.threatId);
    if (base) {
      out.push({
        ...base,
        resolutionKind: r.resolutionKind,
        resolvedAt: r.resolvedAt.toISOString(),
        resolvedByEmail: r.resolvedByEmail,
        note: r.note,
      });
    } else {
      out.push({
        id: r.threatId,
        type: r.threatId.split(':')[0] ?? 'unknown',
        severity: 'amber',
        summary: r.threatId,
        detail: '(source audit row outside current detector window)',
        resolutionKind: r.resolutionKind,
        resolvedAt: r.resolvedAt.toISOString(),
        resolvedByEmail: r.resolvedByEmail,
        note: r.note,
      });
    }
  }
  return out;
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
    // Phase 7A: shared anchor with /api/admin/audit-logs/{timeline,stats}
    // so the Overview's TimelineChartCard, the API's bucket array, and
    // the API's totalEvents stat all reference the same 24-hour window.
    // The rightmost bucket is the current partial hour.
    const w = resolveAuditWindow(TIMELINE_HOURS);

    const rows = await prisma.$queryRaw<RawBucket[]>`
      SELECT
        date_trunc('hour', "timestamp") AS hour,
        COUNT(*)::bigint AS total,
        SUM(CASE WHEN success = false THEN 1 ELSE 0 END)::bigint AS failed
      FROM audit_logs
      WHERE "timestamp" >= ${w.since}
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
    for (let i = 0; i < w.hours; i++) {
      const t = new Date(w.since.getTime() + i * 60 * 60 * 1000);
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
// HIPAA state — Phase 7B: now reads from `hipaa_findings` table.
// ----------------------------------------------------------------------------
// Phase 6Z's getHipaaState() returned a hardcoded array. Phase 7A made
// the card consistent (header badge derived from the same array). Phase
// 7B (this) replaces the hardcoded array with a real query against
// hipaa_findings — the table managed via the new /admin/hipaa page.
//
// Shape returned is unchanged (HipaaState — findings + auditCoverage
// + lastReview), so HipaaComplianceCard + summarizeHipaaFindings keep
// working without UI changes.
//
// Failure mode: returns an "all clear" placeholder if the query throws,
// rather than crashing the Overview SSR. The card visually communicates
// "we're up but the findings query is degraded" via the empty findings
// array → All clear badge.
// ---------------------------------------------------------------------------

interface HipaaFindingRow {
  severity: 'critical' | 'high' | 'medium' | 'low';
  total: bigint;
  resolved: bigint;
}

export async function getHipaaState(): Promise<HipaaState> {
  let lastReviewLabel = 'never';
  let findings: HipaaState['findings'] = [];
  try {
    // GROUP BY severity gives us total + resolved per severity in one
    // round-trip. Constrain to the 3 severities the card surfaces;
    // 'low' rows accumulate but don't get their own card row this turn.
    const rows = await prisma.$queryRaw<HipaaFindingRow[]>`
      SELECT
        severity::text AS severity,
        COUNT(*)::bigint AS total,
        COUNT(*) FILTER (WHERE status = 'resolved')::bigint AS resolved
      FROM hipaa_findings
      WHERE severity IN ('critical', 'high', 'medium')
      GROUP BY severity
    `;

    // Ensure every severity card row has an entry, even when the
    // table has zero findings of that severity (so the card always
    // shows the same 3 rows).
    const map: Record<string, { total: number; resolved: number }> = {};
    for (const r of rows) {
      map[r.severity] = { total: Number(r.total), resolved: Number(r.resolved) };
    }
    findings = (['critical', 'high', 'medium'] as const).map((sev) => ({
      severity: sev,
      total: map[sev]?.total ?? 0,
      resolved: map[sev]?.resolved ?? 0,
    }));

    // "lastReview" = most recent createdAt or resolvedAt across all
    // findings. Surfaces in the card header as "reviewed today / 2d ago".
    const last = await prisma.$queryRaw<{ ts: Date | null }[]>`
      SELECT GREATEST(MAX("createdAt"), MAX("resolvedAt")) AS ts
      FROM hipaa_findings
    `;
    const ts = last[0]?.ts ?? null;
    if (ts) {
      const ageMs = Date.now() - ts.getTime();
      const days = Math.floor(ageMs / (24 * 60 * 60 * 1000));
      lastReviewLabel = days <= 0 ? 'today' : days === 1 ? '1 day ago' : `${days} days ago`;
    }
  } catch (err) {
    console.error('[admin:hipaa] findings query failed:', err);
  }

  return {
    findings,
    // Audit-coverage stat is still hardcoded — the underlying truth
    // ("how many audit actions does the codebase emit") doesn't live in
    // a table yet. Future phase: derive from a manifest of expected
    // AuditAction values vs the set we observe in audit_logs.
    auditCoverage: { covered: 26, total: 26 },
    lastReview: lastReviewLabel,
  };
}
