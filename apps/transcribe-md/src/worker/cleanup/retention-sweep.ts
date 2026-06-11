// ============================================================================
// T-M18.1 A3 — Audio retention sweep
// ----------------------------------------------------------------------------
// HIPAA retention policy, codified:
//
//   SIGNED visits past AUDIO_RETENTION_DAYS have their audio purged
//   (audioKey + dictationAudioKey columns cleared, MinIO objects
//   deleted). Transcripts + SOAP + codes + Rx stay in place — they
//   carry the 7-year retention window the schema already promises via
//   Practice.transcriptRetentionDays = 2555.
//
// Scope of this sweep:
//   - Only SIGNED visits (have signedAt). Unsigned visits are handled
//     by the T-M17.3 stale-visit cleanup (abandoned QUEUED + expired
//     trash).
//   - Skips `deletedAt IS NOT NULL` rows — trash cleanup owns those.
//   - Age threshold measured from `signedAt`, not `createdAt`. A visit
//     that sat in REVIEW for months shouldn't be purged the day it's
//     signed.
//
// Per-practice override:
//   The Practice.audioRetentionDays column exists (default 90) but
//   isn't yet wired into this sweep — the T-M15 audit flagged no UI
//   for per-practice config as finding [3.1], and T-M18.1 A3's
//   decision was to hardcode a single global default first and bolt
//   on per-practice overrides when admin UI lands. TODO: once a
//   practice admin UI exists, change the query to JOIN practices and
//   use each practice's own retention setting.
//
// Env:
//   AUDIO_RETENTION_DAYS         default 90 (3 months)
//   RETENTION_SWEEP_ENABLED      default 'true'
//   RETENTION_SWEEP_CRON         default '0 4 * * *' (4am UTC daily —
//                                offset 1h from T-M17.3 stale-visit
//                                cleanup to avoid DB + MinIO contention)
//
// Log line: `ops:retention-sweep swept { count, userIds }`.
// ============================================================================

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';

import { deleteAudioObject } from '@/lib/minio';
import { log } from '@/lib/log';
import { redactPhi } from '@meddoc/ai';

/** Default audio retention window. 90 days = 3 months.
 *  Rationale: the HIPAA 6-year minimum applies to the clinical
 *  RECORD (transcript + SOAP + codes), not to the audio-evidence
 *  input. The audio's real re-use window is 30-90 days for any
 *  legitimate "wait, what did the patient actually say?" review.
 *  90 days is the value the schema already promises
 *  (Practice.audioRetentionDays @default(90)) AND the value the public
 *  pricing page states ("audio auto-deletes 90 days after the visit is
 *  signed" — apps/marketing/src/app/pricing/pricing-faq.tsx). KEEP THIS
 *  CONSTANT == that copy; the gated retention-sweep-default test
 *  enforces it. (Was a placeholder 180 pre-2026-06-11; it never fired
 *  in prod — at the change the oldest signed visit was 53 days old, so
 *  shortening to 90 deleted nothing.) */
export const DEFAULT_AUDIO_RETENTION_DAYS = 90;

interface RetentionTarget {
  id: string;
  userId: string;
  audioKey: string | null;
  dictationAudioKey: string | null;
  signedAt: Date | null;
}

export interface RetentionSweepResult {
  found: number;
  audioDeleted: number;
  minioFailures: number;
}

function resolveRetentionDays(): number {
  const raw = process.env.AUDIO_RETENTION_DAYS?.trim();
  if (!raw) return DEFAULT_AUDIO_RETENTION_DAYS;
  const n = Number.parseInt(raw, 10);
  // Sanity bounds — don't accept a 0-day accidental config that
  // would nuke every visit's audio on the next tick.
  if (!Number.isFinite(n) || n < 7 || n > 3650) {
    console.warn(
      `[ops:retention-sweep] AUDIO_RETENTION_DAYS=${raw} out of [7, 3650] range — falling back to default ${DEFAULT_AUDIO_RETENTION_DAYS}`
    );
    return DEFAULT_AUDIO_RETENTION_DAYS;
  }
  return n;
}

export async function runRetentionSweep(): Promise<RetentionSweepResult> {
  const retentionDays = resolveRetentionDays();
  const cutoff = new Date(Date.now() - retentionDays * 24 * 60 * 60 * 1000);

  const targets = await prisma.transcribeVisit.findMany({
    where: {
      status: TranscribeVisitStatus.SIGNED,
      signedAt: { lt: cutoff },
      deletedAt: null,
      OR: [
        { audioKey: { not: null } },
        { dictationAudioKey: { not: null } },
      ],
    },
    select: {
      id: true,
      userId: true,
      audioKey: true,
      dictationAudioKey: true,
      signedAt: true,
    },
  });

  if (targets.length === 0) {
    log.info('ops:retention-sweep', 'swept', {
      count: 0,
      audioDeleted: 0,
      minioFailures: 0,
      retentionDays,
    });
    return { found: 0, audioDeleted: 0, minioFailures: 0 };
  }

  // Clear the DB columns first. A crash between the DB update and the
  // MinIO delete would leave orphan objects in the bucket, which the
  // T-M12 sweep catches later. A crash between the MinIO delete and
  // the DB update would leave dangling audioKey values pointing at
  // non-existent objects — much worse for downstream code. So: DB
  // first, MinIO second. One update per target so partial failure on
  // any row doesn't block the others.
  let audioDeleted = 0;
  let minioFailures = 0;
  await Promise.all(
    targets.map(async (t: RetentionTarget) => {
      try {
        await prisma.transcribeVisit.update({
          where: { id: t.id },
          data: {
            audioKey: null,
            dictationAudioKey: null,
          },
        });
      } catch (err) {
        console.error(
          '[ops:retention-sweep] column clear failed:',
          redactPhi(err instanceof Error ? err.message : err)
        );
        return; // skip MinIO — keep the object so we can retry later
      }

      const keys = [t.audioKey, t.dictationAudioKey].filter(
        (k): k is string => typeof k === 'string' && k.length > 0
      );
      await Promise.all(
        keys.map(async (key) => {
          try {
            await deleteAudioObject(key);
            audioDeleted += 1;
          } catch (err) {
            minioFailures += 1;
            console.warn(
              `[ops:retention-sweep] minio delete failed key=${key}:`,
              redactPhi(err instanceof Error ? err.message : err)
            );
          }
        })
      );
    })
  );

  log.info('ops:retention-sweep', 'swept', {
    count: targets.length,
    audioDeleted,
    minioFailures,
    retentionDays,
    userIds: [...new Set(targets.map((t: RetentionTarget) => t.userId))],
  });

  return {
    found: targets.length,
    audioDeleted,
    minioFailures,
  };
}
