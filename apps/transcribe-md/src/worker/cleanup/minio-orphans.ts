// ============================================================================
// MinIO orphan-object cleanup (T-M12)
// ----------------------------------------------------------------------------
// Reconciles the transcribe-md-audio bucket against the DB: any object
// that no `transcribe_visits` row references AND is older than the
// retention window gets deleted. Everything else is kept.
//
// Why it's safe
//   1. Referenced objects (audioKey or dictationAudioKey) are always
//      kept regardless of age.
//   2. Unreferenced objects younger than retentionDays are kept. This
//      is the race guard: an upload that just landed in MinIO might
//      not have its Prisma row written yet (the upload route writes
//      MinIO then Prisma). retentionDays must be longer than any
//      conceivable in-flight upload — 30 days is deliberately loose.
//   3. Dry-run mode logs everything but calls zero deleteObject().
//      Ops use this on the first prod run to sanity-check the
//      delete list before flipping the live mode on.
//
// Failure mode
//   If the Prisma query throws, we abort with zero deletions — better
//   to skip a run than to delete based on a partial reference set.
//   Individual deleteAudioObject failures are logged and the sweep
//   continues; the next run picks up the leftover.
// ============================================================================

import prisma from '@meddoc/db';

import {
  deleteAudioObject,
  listAllAudioObjects,
  type MinioObjectInfo,
} from '@/lib/minio';

export interface CleanupOptions {
  /** Minimum age (in days) before an orphan is eligible for deletion.
   *  Guards against racing an in-flight upload. Default 30 in production;
   *  tests pass a small value to exercise the age filter. */
  retentionDays: number;
  /** When true: log what WOULD be deleted, don't actually remove. */
  dryRun: boolean;
  /** Optional clock override for tests — lets the test fix "now" so
   *  lastModified math is deterministic. Real callers pass undefined. */
  nowMs?: number;
}

export interface CleanupResult {
  /** Objects that have a matching TranscribeVisit row. */
  kept: number;
  /** Objects deleted (or would-be-deleted in dry-run). */
  deleted: number;
  /** Orphans younger than retentionDays — kept for safety. */
  skippedYoung: number;
  /** Sum of `size` bytes across `deleted`. 0 for items with unknown size. */
  totalReclaimedBytes: number;
  /** Per-object delete failures. Empty on a clean run. */
  failures: Array<{ key: string; error: string }>;
}

const DAY_MS = 24 * 60 * 60 * 1000;
const LOG = '[ops:minio-cleanup]';

/** Collect every audio key referenced by any TranscribeVisit row into a
 *  single Set. One query, no n+1. Null/empty strings are excluded. */
async function loadReferencedKeys(): Promise<Set<string>> {
  const rows = await prisma.transcribeVisit.findMany({
    select: { audioKey: true, dictationAudioKey: true },
  });
  const out = new Set<string>();
  for (const r of rows) {
    if (r.audioKey && r.audioKey.length > 0) out.add(r.audioKey);
    if (r.dictationAudioKey && r.dictationAudioKey.length > 0) {
      out.add(r.dictationAudioKey);
    }
  }
  return out;
}

function decideAction(
  obj: MinioObjectInfo,
  referenced: Set<string>,
  cutoffMs: number
): 'keep' | 'delete' | 'skip-young' {
  if (referenced.has(obj.name)) return 'keep';
  const lastModifiedMs = obj.lastModified?.getTime();
  if (lastModifiedMs === undefined) {
    // Unknown age — skip conservatively. MinIO should always return
    // lastModified on listObjects; the ?? covers SDK quirks.
    return 'skip-young';
  }
  if (lastModifiedMs > cutoffMs) return 'skip-young';
  return 'delete';
}

export async function runMinioOrphanCleanup(
  opts: CleanupOptions
): Promise<CleanupResult> {
  const nowMs = opts.nowMs ?? Date.now();
  const cutoffMs = nowMs - opts.retentionDays * DAY_MS;

  console.log(
    `${LOG} starting: retentionDays=${opts.retentionDays} dryRun=${opts.dryRun} cutoff=${new Date(cutoffMs).toISOString()}`
  );

  const referenced = await loadReferencedKeys();
  console.log(`${LOG} loaded ${referenced.size} referenced keys from DB`);

  const objects = await listAllAudioObjects();
  console.log(`${LOG} listing found ${objects.length} MinIO objects`);

  let kept = 0;
  let deleted = 0;
  let skippedYoung = 0;
  let totalReclaimedBytes = 0;
  const failures: CleanupResult['failures'] = [];

  for (const obj of objects) {
    const action = decideAction(obj, referenced, cutoffMs);
    if (action === 'keep') {
      kept++;
      continue;
    }
    if (action === 'skip-young') {
      skippedYoung++;
      continue;
    }

    // action === 'delete' — orphan, old enough.
    const size = obj.size ?? 0;
    const ageDays = obj.lastModified
      ? Math.floor((nowMs - obj.lastModified.getTime()) / DAY_MS)
      : -1;
    const verb = opts.dryRun ? 'WOULD DELETE' : 'DELETED';

    if (!opts.dryRun) {
      try {
        await deleteAudioObject(obj.name);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        console.error(
          `${LOG} delete failed for ${obj.name}: ${msg} — skipping, next run will retry`
        );
        failures.push({ key: obj.name, error: msg });
        continue;
      }
    }
    deleted++;
    totalReclaimedBytes += size;
    console.log(
      `${LOG} ${verb} ${obj.name} (${size} bytes, age ${ageDays}d)`
    );
  }

  const summary: CleanupResult = {
    kept,
    deleted,
    skippedYoung,
    totalReclaimedBytes,
    failures,
  };
  console.log(
    `${LOG} done: kept=${summary.kept} ` +
      `deleted=${summary.deleted} skippedYoung=${summary.skippedYoung} ` +
      `bytesReclaimed=${summary.totalReclaimedBytes} ` +
      `failures=${summary.failures.length} ` +
      `dryRun=${opts.dryRun}`
  );
  return summary;
}
