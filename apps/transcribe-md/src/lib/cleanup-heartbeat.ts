// ============================================================================
// Cleanup-cron heartbeat helpers (T-M18.2 A13)
// ----------------------------------------------------------------------------
// The T-M17.3 / T-M18.1 cleanup crons log a structured "swept" line on
// every run. A silently-failing cron (worker dies after scheduling but
// before the first tick, BullMQ scheduler glitch, …) would produce NO
// line, which looks identical to "the worker started 2 seconds ago and
// hasn't ticked yet."
//
// This helper writes a short Redis key per cron name right after each
// successful run. /api/health reads those keys and reports each cron's
// `ageSeconds` so a monitoring dashboard can alert when any cron's
// age exceeds its expected period + grace window.
//
// Keys live under `transcribe-md:cleanup:last-ran:<name>`. No TTL —
// we want the key to persist across worker restarts. The value is a
// JSON blob with `ranAt` (epoch ms) + a small result summary.
//
// Not Prisma-backed because the worker already owns a Redis connection
// (BullMQ) and the read-side lives in the web's /api/health handler
// (which also has Redis). Avoiding a round-trip to Postgres keeps the
// health probe fast.
// ============================================================================

import { getSharedRedisConnection } from '@/lib/queue';

/** Well-known cleanup-cron names. Keep in sync with the worker's
 *  scheduler registrations — a rename here without a rename there
 *  surfaces as a missing heartbeat on the next health probe. */
export type CleanupJobName =
  | 'stale-visit-cleanup'
  | 'retention-sweep'
  | 'minio-orphan-cleanup';

interface HeartbeatPayload {
  /** Epoch ms when the run completed. */
  ranAt: number;
  /** Free-form result snapshot. Shape varies by cron; callers pass
   *  whatever makes most sense in their log line. Kept small —
   *  numbers + short strings, no unbounded blobs. */
  result?: Record<string, unknown>;
}

function keyFor(name: CleanupJobName): string {
  return `transcribe-md:cleanup:last-ran:${name}`;
}

/** Write-side — called by the worker right after each sweep finishes.
 *  Fire-and-forget from the caller's perspective; a Redis hiccup
 *  here should NEVER fail the sweep (which already wrote its own
 *  log line and updated DB state). */
export async function recordCleanupHeartbeat(
  name: CleanupJobName,
  result?: Record<string, unknown>
): Promise<void> {
  try {
    const payload: HeartbeatPayload = {
      ranAt: Date.now(),
      result,
    };
    await getSharedRedisConnection().set(
      keyFor(name),
      JSON.stringify(payload)
    );
  } catch (err) {
    console.warn(
      `[cleanup-heartbeat] set failed name=${name}:`,
      err instanceof Error ? err.message : err
    );
  }
}

export interface HeartbeatSnapshot {
  name: CleanupJobName;
  /** `null` when the key is missing (cron has never run on this
   *  Redis instance) — distinct from "ran a long time ago". */
  ageSeconds: number | null;
  ranAt?: string;
  result?: Record<string, unknown>;
}

/** Read-side — called by /api/health. Returns one snapshot per
 *  known cron. Errors resolve to `ageSeconds: null` so the health
 *  response degrades gracefully rather than 500ing on a missing
 *  key. */
export async function readCleanupHeartbeats(): Promise<HeartbeatSnapshot[]> {
  const names: CleanupJobName[] = [
    'stale-visit-cleanup',
    'retention-sweep',
    'minio-orphan-cleanup',
  ];
  const redis = getSharedRedisConnection();
  const now = Date.now();
  const raw = await Promise.all(
    names.map(async (name): Promise<HeartbeatSnapshot> => {
      try {
        const v = await redis.get(keyFor(name));
        if (!v) return { name, ageSeconds: null };
        const parsed = JSON.parse(v) as HeartbeatPayload;
        return {
          name,
          ageSeconds: Math.max(0, Math.floor((now - parsed.ranAt) / 1000)),
          ranAt: new Date(parsed.ranAt).toISOString(),
          result: parsed.result,
        };
      } catch {
        return { name, ageSeconds: null };
      }
    })
  );
  return raw;
}
