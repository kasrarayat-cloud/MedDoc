// ============================================================================
// /admin/usage — server-side data layer
// ----------------------------------------------------------------------------
// The first three fetchers mirror exactly what /api/admin/usage/{summary,
// timeline, by-user} compute. They share the `resolveWindow` helper from
// the API folder so the math is identical.
//
// `fetchAnomalies` does its own SQL — there's no /api/admin/anomalies
// endpoint yet (Phase 6A backend stopped at user-mgmt + cost rollups).
// Two detectors:
//   user_spike            — last-24h spend > 5× the user's 7-day daily
//                           average AND > $5 in absolute terms
//   api_failure_burst     — any 15-minute window in the last 24h with
//                           >10 failed ai_calls for one provider
// ============================================================================

import 'server-only';

import { assertSuperAdminCaller } from '@/app/admin/_lib/admin-gate';

import prisma from '@meddoc/db';

import {
  resolveWindow,
  type WindowKey,
} from '../../../api/admin/_usage-window';
import type {
  Anomaly,
  TimelineResponse,
  TopUsersResponse,
  UsageSummary,
} from '../_types';

const HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * HOUR_MS;

// ── summary ───────────────────────────────────────────────────────────────

interface ProvRow {
  provider: string;
  operation: string;
  total: number;
  events: bigint;
}

export async function fetchUsageSummary(window: WindowKey): Promise<UsageSummary> {
  await assertSuperAdminCaller();
  const w = resolveWindow(window);
  const prev = resolveWindow(window, { offset: 1 });

  const [rows, prevRows] = await Promise.all([
    prisma.$queryRaw<ProvRow[]>`
      SELECT provider, operation,
             SUM("totalCostUsd")::float AS total,
             COUNT(*)::bigint           AS events
      FROM api_usage_events
      WHERE timestamp >= ${w.since} AND timestamp < ${w.until}
      GROUP BY provider, operation
    `.catch(() => [] as ProvRow[]),
    prisma.$queryRaw<{ total: number }[]>`
      SELECT SUM("totalCostUsd")::float AS total
      FROM api_usage_events
      WHERE timestamp >= ${prev.since} AND timestamp < ${prev.until}
    `.catch(() => [{ total: 0 }] as { total: number }[]),
  ]);

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
  const prevTotal = Number(prevRows[0]?.total ?? 0);
  const percentChange =
    prevTotal > 0 ? ((totalCostUsd - prevTotal) / prevTotal) * 100 : null;

  return {
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
  };
}

// ── timeline ──────────────────────────────────────────────────────────────

interface BucketRow {
  bucket: Date;
  provider: string;
  total: number;
  events: bigint;
}

export async function fetchTimeline(
  window: WindowKey,
  granularity?: 'hour' | 'day'
): Promise<TimelineResponse> {
  await assertSuperAdminCaller();
  const gran =
    granularity ?? (window === '24h' ? 'hour' : 'day');
  const w = resolveWindow(window);

  const rows =
    gran === 'hour'
      ? await prisma.$queryRaw<BucketRow[]>`
          SELECT date_trunc('hour', timestamp) AS bucket, provider,
                 SUM("totalCostUsd")::float AS total,
                 COUNT(*)::bigint            AS events
          FROM api_usage_events
          WHERE timestamp >= ${w.since} AND timestamp < ${w.until}
          GROUP BY 1, 2
          ORDER BY 1 ASC
        `.catch(() => [] as BucketRow[])
      : await prisma.$queryRaw<BucketRow[]>`
          SELECT date_trunc('day', timestamp) AS bucket, provider,
                 SUM("totalCostUsd")::float AS total,
                 COUNT(*)::bigint            AS events
          FROM api_usage_events
          WHERE timestamp >= ${w.since} AND timestamp < ${w.until}
          GROUP BY 1, 2
          ORDER BY 1 ASC
        `.catch(() => [] as BucketRow[]);

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

  return {
    window,
    granularity: gran,
    since: w.since.toISOString(),
    until: w.until.toISOString(),
    buckets,
  };
}

// ── top users ─────────────────────────────────────────────────────────────

interface TopUserRowRaw {
  userId: string | null;
  userEmail: string | null;
  total: number;
  events: bigint;
}

export async function fetchTopUsers(
  window: WindowKey,
  limit = 10
): Promise<TopUsersResponse> {
  await assertSuperAdminCaller();
  const w = resolveWindow(window);
  const rows = await prisma.$queryRaw<TopUserRowRaw[]>`
    SELECT e."userId" AS "userId",
           u.email   AS "userEmail",
           SUM(e."totalCostUsd")::float AS total,
           COUNT(*)::bigint              AS events
    FROM api_usage_events e
    LEFT JOIN users u ON u.id = e."userId"
    WHERE e.timestamp >= ${w.since} AND e.timestamp < ${w.until}
    GROUP BY e."userId", u.email
    ORDER BY total DESC, events DESC
    LIMIT ${limit}
  `.catch(() => [] as TopUserRowRaw[]);

  return {
    window,
    since: w.since.toISOString(),
    until: w.until.toISOString(),
    sortBy: 'cost',
    rows: rows.map((r: TopUserRowRaw) => ({
      userId: r.userId,
      userEmail:
        r.userEmail ?? (r.userId ? '(deleted user)' : '(unattributed)'),
      totalCostUsd: round4(Number(r.total ?? 0)),
      events: Number(r.events ?? 0),
    })),
  };
}

// ── anomalies ─────────────────────────────────────────────────────────────

interface SpikeRow {
  userId: string;
  userEmail: string | null;
  total: number;
}
interface BurstRow {
  provider: string;
  count: bigint;
  bucket_start: Date;
}

export async function fetchAnomalies(): Promise<Anomaly[]> {
  await assertSuperAdminCaller();
  const now = Date.now();
  const since24h = new Date(now - DAY_MS);
  const since7d = new Date(now - 7 * DAY_MS);

  const [day24, week7, bursts] = await Promise.all([
    prisma.$queryRaw<SpikeRow[]>`
      SELECT e."userId" AS "userId",
             u.email   AS "userEmail",
             SUM(e."totalCostUsd")::float AS total
      FROM api_usage_events e
      LEFT JOIN users u ON u.id = e."userId"
      WHERE e.timestamp >= ${since24h} AND e."userId" IS NOT NULL
      GROUP BY e."userId", u.email
      HAVING SUM(e."totalCostUsd") > 5
    `.catch(() => [] as SpikeRow[]),
    prisma.$queryRaw<{ userId: string; total: number }[]>`
      SELECT "userId", SUM("totalCostUsd")::float AS total
      FROM api_usage_events
      WHERE timestamp >= ${since7d} AND "userId" IS NOT NULL
      GROUP BY "userId"
    `.catch(() => [] as { userId: string; total: number }[]),
    prisma.$queryRaw<BurstRow[]>`
      SELECT
        lower(provider) AS provider,
        COUNT(*)::bigint AS count,
        DATE_TRUNC('minute', "createdAt")
          - (EXTRACT(MINUTE FROM "createdAt")::int % 15) * INTERVAL '1 minute'
          AS bucket_start
      FROM ai_calls
      WHERE "createdAt" >= ${since24h} AND success = false
      GROUP BY 1, 3
      HAVING COUNT(*) > 10
      ORDER BY bucket_start DESC
      LIMIT 10
    `.catch(() => [] as BurstRow[]),
  ]);

  const week7By = new Map<string, number>();
  for (const r of week7) week7By.set(r.userId, Number(r.total ?? 0) / 7);

  const userSpikes: Anomaly[] = [];
  for (const r of day24) {
    const today = Number(r.total ?? 0);
    const avg = week7By.get(r.userId) ?? 0;
    if (today > 5 * avg && today > 5) {
      userSpikes.push({
        kind: 'user_spike',
        userId: r.userId,
        userName: r.userEmail ?? r.userId,
        todayUsd: round4(today),
        avgDailyUsd: round4(avg),
      });
    }
  }

  const failureBursts: Anomaly[] = bursts.map((b: BurstRow) => {
    const start = b.bucket_start;
    const end = new Date(start.getTime() + 15 * 60 * 1000);
    const fmt = (d: Date) =>
      `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`;
    return {
      kind: 'api_failure_burst',
      provider: b.provider,
      count: Number(b.count),
      windowLabel: `${fmt(start)}–${fmt(end)} UTC`,
    };
  });

  return [...failureBursts, ...userSpikes].slice(0, 10);
}

// ── small utils ───────────────────────────────────────────────────────────

function round4(n: number): number {
  return Math.round(n * 10_000) / 10_000;
}
function roundEach(o: Record<string, number>): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [k, v] of Object.entries(o)) out[k] = round4(v);
  return out;
}
