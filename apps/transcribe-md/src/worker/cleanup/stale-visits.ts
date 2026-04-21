// ============================================================================
// T-M17.3 stale-visit cleanup sweeps (+ T-M18.2 A5 account-deletion purge)
// ----------------------------------------------------------------------------
// Three sweeps run as a single BullMQ cron job (daily at 3am UTC):
//
//   Sweep 1 — Abandoned QUEUED drafts (resolves KI-3)
//     WHERE status='QUEUED'
//       AND audioKey IS NULL
//       AND dictationAudioKey IS NULL
//       AND (rawTextInput IS NULL OR rawTextInput = '')
//       AND createdAt < now() - 24 hours
//
//   Sweep 2 — Expired trash (15-day window from T-M17.3 soft-delete)
//     WHERE deletedAt IS NOT NULL
//       AND deletedAt < now() - 15 days
//
//   Sweep 3 — Expired AccountDeletion audit rows (T-M18.2 A5; the 90d
//     retention the settings/delete-account flow promises)
//     WHERE purgeAt < now()
//
// Visit sweeps do their DB work in one transaction per sweep (AiCall.
// deleteMany + TranscribeVisit.deleteMany by id set). MinIO sweep runs
// after the transaction commits; failures there are logged best-effort
// because the T-M12 orphan sweeper handles stragglers anyway.
// ============================================================================

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';

import { deleteAudioObject } from '@/lib/minio';
import { log } from '@/lib/log';
import { redactPhi } from '@meddoc/ai';

/** Abandoned-QUEUED age threshold. Shorter than the trash window —
 *  a draft with zero input is either mis-clicked (doctor bails out
 *  of /visits/new) or intentionally orphaned. 24h gives a user who
 *  left a tab open overnight a clean window to come back. */
const ABANDONED_QUEUED_WINDOW_HOURS = 24;

/** Trash retention window — T-M17.3 soft-delete contract. The
 *  banner on /visits/[id] and the countdown chip on the Trash tab
 *  both compute their display against this constant. If you change
 *  it, update visit-lifecycle-actions.tsx + trashed-visit-card.tsx
 *  too. */
const TRASH_RETENTION_DAYS = 15;

interface StaleVisitTarget {
  id: string;
  userId: string;
  audioKey: string | null;
  dictationAudioKey: string | null;
}

export interface SweepResult {
  found: number;
  deleted: number;
  minioFailures: number;
}

async function purgeTargets(
  targets: StaleVisitTarget[],
  scope: string
): Promise<SweepResult> {
  if (targets.length === 0) {
    return { found: 0, deleted: 0, minioFailures: 0 };
  }

  const ids = targets.map((t) => t.id);
  let deleted = 0;
  try {
    const result = await prisma.$transaction(async (tx: typeof prisma) => {
      await tx.aiCall.deleteMany({ where: { visitId: { in: ids } } });
      const d = await tx.transcribeVisit.deleteMany({
        where: { id: { in: ids } },
      });
      return d.count;
    });
    deleted = result;
  } catch (err) {
    console.error(
      `[${scope}] purge tx failed for ${ids.length} row(s):`,
      redactPhi(err instanceof Error ? err.message : err)
    );
    return { found: targets.length, deleted: 0, minioFailures: 0 };
  }

  // Best-effort MinIO sweep. Parallelised per row; individual failures
  // accumulate in the counter but never fail the sweep. T-M12 orphan
  // cleanup will eventually catch anything we miss here.
  let minioFailures = 0;
  await Promise.all(
    targets.flatMap((t) =>
      [t.audioKey, t.dictationAudioKey].map(async (key) => {
        if (!key) return;
        try {
          await deleteAudioObject(key);
        } catch (err) {
          minioFailures += 1;
          console.warn(
            `[${scope}] minio delete failed key=${key}:`,
            redactPhi(err instanceof Error ? err.message : err)
          );
        }
      })
    )
  );

  return { found: targets.length, deleted, minioFailures };
}

async function sweepAbandonedQueued(): Promise<SweepResult> {
  const cutoff = new Date(
    Date.now() - ABANDONED_QUEUED_WINDOW_HOURS * 60 * 60 * 1000
  );
  // The rawTextInput column is Text — empty-string is functionally
  // the same as null for "no input". Capture both in the predicate.
  const targets = await prisma.transcribeVisit.findMany({
    where: {
      status: TranscribeVisitStatus.QUEUED,
      audioKey: null,
      dictationAudioKey: null,
      OR: [{ rawTextInput: null }, { rawTextInput: '' }],
      createdAt: { lt: cutoff },
    },
    select: {
      id: true,
      userId: true,
      audioKey: true,
      dictationAudioKey: true,
    },
  });
  const result = await purgeTargets(targets, 'cleanup:abandoned-queued');
  log.info('cleanup:abandoned-queued', 'swept', {
    found: result.found,
    deleted: result.deleted,
    minioFailures: result.minioFailures,
    olderThanHours: ABANDONED_QUEUED_WINDOW_HOURS,
    userIds: [...new Set(targets.map((t: StaleVisitTarget) => t.userId))],
  });
  return result;
}

async function sweepExpiredTrash(): Promise<SweepResult> {
  const cutoff = new Date(
    Date.now() - TRASH_RETENTION_DAYS * 24 * 60 * 60 * 1000
  );
  const targets = await prisma.transcribeVisit.findMany({
    where: {
      deletedAt: { lt: cutoff },
    },
    select: {
      id: true,
      userId: true,
      audioKey: true,
      dictationAudioKey: true,
    },
  });
  const result = await purgeTargets(targets, 'cleanup:expired-trash');
  log.info('cleanup:expired-trash', 'swept', {
    found: result.found,
    deleted: result.deleted,
    minioFailures: result.minioFailures,
    olderThanDays: TRASH_RETENTION_DAYS,
    userIds: [...new Set(targets.map((t: StaleVisitTarget) => t.userId))],
  });
  return result;
}

/** T-M18.2 A5 — delete AccountDeletion audit rows whose `purgeAt`
 *  has passed. The delete-account flow writes these with `purgeAt =
 *  now + 90d` as the HIPAA-adjacent audit record of "user asked to
 *  be forgotten on this date, here's what they left behind (email,
 *  visit count, specialty)". The schema promises to purge after
 *  90 days — this sweep is what makes that promise real.
 *
 *  No MinIO side effects (audit row has no external bytes). No
 *  transaction needed — deleteMany is atomic at the row-set level. */
async function sweepExpiredAccountDeletions(): Promise<{
  found: number;
  deleted: number;
}> {
  const expired = await prisma.accountDeletion.findMany({
    where: { purgeAt: { lt: new Date() } },
    select: { id: true, userId: true },
  });
  if (expired.length === 0) {
    log.info('cleanup:expired-account-deletions', 'swept', {
      found: 0,
      deleted: 0,
    });
    return { found: 0, deleted: 0 };
  }
  let deleted = 0;
  try {
    const d = await prisma.accountDeletion.deleteMany({
      where: { id: { in: expired.map((r: { id: string }) => r.id) } },
    });
    deleted = d.count;
  } catch (err) {
    console.error(
      '[cleanup:expired-account-deletions] purge failed:',
      redactPhi(err instanceof Error ? err.message : err)
    );
  }
  log.info('cleanup:expired-account-deletions', 'swept', {
    found: expired.length,
    deleted,
    // userIds here are EX-users (rows exist because the user deleted
    // themselves); logging the userIds helps support reconstruct a
    // timeline if a question comes up within the 90-day window.
    userIds: expired.map((r: { userId: string }) => r.userId),
  });
  return { found: expired.length, deleted };
}

export async function runStaleVisitCleanup(): Promise<{
  abandoned: SweepResult;
  trash: SweepResult;
  accountDeletions: { found: number; deleted: number };
}> {
  const abandoned = await sweepAbandonedQueued();
  const trash = await sweepExpiredTrash();
  const accountDeletions = await sweepExpiredAccountDeletions();
  return { abandoned, trash, accountDeletions };
}
