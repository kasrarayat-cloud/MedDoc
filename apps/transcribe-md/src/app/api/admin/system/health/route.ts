// ============================================================================
// GET /api/admin/system/health — container + datastore liveness snapshot
// ----------------------------------------------------------------------------
// Best-effort: each section returns null on failure rather than tripping
// the whole endpoint. The dashboard surfaces null sections as "unknown"
// rather than red — flapping liveness shouldn't poison the page.
//
// Containers: we don't have docker-socket access from this app, so the
// best signal we can offer without privilege escalation is the in-DB
// liveness of postgres (we just queried it), the in-Redis liveness of
// redis (PING), and a HEAD probe against MinIO. The other containers
// (transcribe-md, transcribe-md-worker, marketing, meddoc-pro itself,
// caddy) are inferred from the ingress side: marketing/meddoc-pro/
// transcribe-md must be up if we're returning at all (we ARE the
// meddoc-pro container), and caddy must be up if the request reached
// us via HTTPS.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';
import { getRedis } from '@/lib/redis';

interface PgRow {
  active_connections: bigint;
  idle_connections: bigint;
  db_size_bytes: bigint;
}

export const dynamic = 'force-dynamic';

export const GET = adminApi('system:health', async () => {
  const [database, redis, minio] = await Promise.all([
    inspectDatabase(),
    inspectRedis(),
    inspectMinio(),
  ]);

  return NextResponse.json({
    containers: [
      { name: 'meddoc-pro', healthy: true, source: 'self' },
      { name: 'postgres', healthy: database !== null, source: 'query' },
      { name: 'redis', healthy: redis !== null, source: 'ping' },
      { name: 'minio', healthy: minio !== null, source: 'http-head' },
    ],
    database,
    redis,
    minio,
  });
});

async function inspectDatabase(): Promise<{
  connectionsActive: number;
  connectionsIdle: number;
  sizeBytes: number;
} | null> {
  try {
    const rows = await prisma.$queryRaw<PgRow[]>`
      SELECT
        COUNT(*) FILTER (WHERE state = 'active')::bigint AS active_connections,
        COUNT(*) FILTER (WHERE state = 'idle')::bigint   AS idle_connections,
        pg_database_size(current_database())::bigint     AS db_size_bytes
      FROM pg_stat_activity
      WHERE datname = current_database()
    `;
    const r = rows[0];
    if (!r) return null;
    return {
      connectionsActive: Number(r.active_connections),
      connectionsIdle: Number(r.idle_connections),
      sizeBytes: Number(r.db_size_bytes),
    };
  } catch (err) {
    console.error('[admin:health] db inspect failed:', err);
    return null;
  }
}

async function inspectRedis(): Promise<{
  keyCount: number;
  memoryUsedMb: number;
  queueLengths: Record<string, number>;
} | null> {
  try {
    const r = getRedis();
    // PING shouldn't error on a live connection; treat it as the
    // canary. dbsize + memory are measured separately so a single
    // missing one doesn't take the whole section down.
    const pong = await r.ping();
    if (pong !== 'PONG') return null;
    const dbsize = await r.dbsize().catch(() => -1);
    const info = await r.info('memory').catch(() => '');
    const usedRaw =
      info.match(/used_memory:(\d+)/)?.[1];
    const memoryUsedMb = usedRaw
      ? Math.round((Number.parseInt(usedRaw, 10) / 1_048_576) * 10) / 10
      : 0;

    // BullMQ queue depths — `wait` is the canonical "pending jobs"
    // counter. Names match what apps/transcribe-md/src/lib/queue.ts
    // and the worker boot logs use.
    const [tmWait, cleanupWait] = await Promise.all([
      r.llen('bull:transcribe-md:wait').catch(() => 0),
      r.llen('bull:transcribe-md-cleanup:wait').catch(() => 0),
    ]);

    return {
      keyCount: dbsize >= 0 ? dbsize : 0,
      memoryUsedMb,
      queueLengths: {
        'transcribe-md': tmWait,
        'transcribe-md-cleanup': cleanupWait,
      },
    };
  } catch (err) {
    console.error('[admin:health] redis inspect failed:', err);
    return null;
  }
}

async function inspectMinio(): Promise<{
  endpoint: string;
  reachable: boolean;
} | null> {
  // Poke MinIO's well-known cluster endpoint via HTTP HEAD. We don't
  // need bucket counts for a pilot — just liveness. Object-count
  // stats can land in a Phase 2 endpoint if Ops decides they're
  // worth the round-trip.
  const endpoint =
    process.env.MINIO_ENDPOINT?.trim() || 'minio:9000';
  const useSsl =
    (process.env.MINIO_USE_SSL?.trim().toLowerCase() ?? 'false') === 'true';
  const url = `${useSsl ? 'https' : 'http'}://${endpoint}/minio/health/live`;
  try {
    const res = await fetch(url, {
      method: 'GET',
      // Short-circuit before the request stalls if MinIO is down.
      signal: AbortSignal.timeout(2_000),
    });
    return { endpoint, reachable: res.ok };
  } catch {
    return null;
  }
}
