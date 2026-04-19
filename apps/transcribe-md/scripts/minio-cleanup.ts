// ============================================================================
// Manual MinIO orphan cleanup runner (T-M12)
// ----------------------------------------------------------------------------
// Invoke from inside the transcribe-md-worker container:
//   docker compose exec transcribe-md-worker npx tsx scripts/minio-cleanup.ts
//
// Or from the host via the npm script:
//   npm run minio:cleanup -w transcribe-md
//
// Reads the same env vars the scheduled run uses:
//   MINIO_ORPHAN_CLEANUP_DRY_RUN           default 'true'
//   MINIO_ORPHAN_CLEANUP_RETENTION_DAYS    default 30
//
// Ops workflow
//   1. First run: leave MINIO_ORPHAN_CLEANUP_DRY_RUN=true. Review the
//      [ops:minio-cleanup] WOULD DELETE lines.
//   2. If the list looks right, set DRY_RUN=false and re-run.
//   3. Confirm totals look sane (totalReclaimedBytes, kept, deleted).
// ============================================================================

import 'dotenv/config';

import { runMinioOrphanCleanup } from '../src/worker/cleanup/minio-orphans';

async function main() {
  const dryRun =
    (process.env.MINIO_ORPHAN_CLEANUP_DRY_RUN ?? 'true').toLowerCase() !==
    'false';
  const retentionDays = Number.parseInt(
    process.env.MINIO_ORPHAN_CLEANUP_RETENTION_DAYS ?? '30',
    10
  );

  const result = await runMinioOrphanCleanup({ dryRun, retentionDays });
  console.log('---');
  console.log(JSON.stringify(result, null, 2));
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error('[minio-cleanup] fatal:', err);
    process.exit(1);
  });
