// ============================================================================
// Worker: retention_purge (M7)
// ----------------------------------------------------------------------------
// BullMQ repeatable — runs daily at 02:00 UTC per M7 D3. For every
// practice, scans for ScribeVisit rows past their audio / transcript
// retention windows, emits a per-practice dry-run log line:
//
//   {practiceId, audioCount, transcriptCount, oldestSignedAt, safetyExcludedCount}
//
// When RETENTION_PURGE_LIVE=true, additionally deletes MinIO objects +
// soft-deletes transcripts/outputs + flips ScribeVisit.deletedAt, AND
// emits a Sentry info-level message with the counts so the purge is
// auditable outside our own DB (M7 D8 addition).
// ============================================================================

import * as Sentry from '@sentry/nextjs';
import prisma from '@meddoc/db';
import { getMinio, SCRIBE_BUCKET } from '@/lib/minio';
import {
  scanPracticeRetention,
  type RetentionScanResult,
} from '@/server/retention/query';

export interface RetentionPurgePayload {
  /** Test hook — override the clock so cron runs don't collide with live. */
  now?: string;
}

function isLiveMode(): boolean {
  return (process.env.RETENTION_PURGE_LIVE ?? '').trim().toLowerCase() === 'true';
}

function logScan(r: RetentionScanResult, live: boolean): void {
  // Single-line JSON for grep-ability in container logs.
  console.log(
    `[retention_purge] ${live ? 'LIVE' : 'DRY_RUN'} ` +
      JSON.stringify({
        practiceId: r.practiceId,
        audioCount: r.audioCount,
        transcriptCount: r.transcriptCount,
        safetyExcludedCount: r.safetyExcludedCount,
        oldestSignedAt: r.oldestSignedAt,
        audioCutoff: r.audioCutoff.toISOString(),
        transcriptCutoff: r.transcriptCutoff.toISOString(),
      })
  );
}

export async function runRetentionPurge(
  payload: RetentionPurgePayload = {}
): Promise<void> {
  const live = isLiveMode();
  const now = payload.now ? new Date(payload.now) : new Date();

  // Per-practice so the log line names a specific tenant and one
  // misconfigured retention on one practice can't silently stop others
  // from being scanned.
  const practices = await prisma.practice.findMany({
    where: { isActive: true },
    select: {
      id: true,
      audioRetentionDays: true,
      transcriptRetentionDays: true,
    },
  });

  let totalAudio = 0;
  let totalTranscripts = 0;
  let totalSafetyExcluded = 0;

  for (const p of practices) {
    const result = await scanPracticeRetention(
      prisma,
      p.id,
      {
        audioRetentionDays: p.audioRetentionDays,
        transcriptRetentionDays: p.transcriptRetentionDays,
      },
      now
    );
    logScan(result, live);
    totalAudio += result.audioCount;
    totalTranscripts += result.transcriptCount;
    totalSafetyExcluded += result.safetyExcludedCount;

    if (live && (result.audioCount > 0 || result.transcriptCount > 0)) {
      await executePurge(p.id, result);
    }
  }

  if (live) {
    // M7 D8 addition — Sentry info-level message so a purge leaves a
    // tamper-evident trail outside the DB we just mutated. No-op if
    // Sentry isn't initialized.
    Sentry.captureMessage(
      `[retention] Live purge completed. audio=${totalAudio} transcripts=${totalTranscripts} safetyExcluded=${totalSafetyExcluded}`,
      {
        level: 'info',
        tags: { feature: 'retention', mode: 'live' },
        extra: {
          totalAudio,
          totalTranscripts,
          totalSafetyExcluded,
          practiceCount: practices.length,
          ranAt: now.toISOString(),
        },
      }
    );
  }
}

/**
 * Actually delete audio + soft-delete scribe rows. Only called when
 * RETENTION_PURGE_LIVE=true. Deliberately kept small + obvious so
 * unsafe mutations are easy to audit.
 */
async function executePurge(
  practiceId: string,
  result: RetentionScanResult
): Promise<void> {
  const minio = getMinio();

  // --- Audio objects ---
  if (result.audioSample.length > 0) {
    // Pull the full list (not just the sample) via a second query to
    // avoid race with a live visit that just ended.
    const audioVisits = await prisma.scribeVisit.findMany({
      where: {
        practiceId,
        deletedAt: null,
        audioObjectKey: { not: null },
        endedAt: { lt: result.audioCutoff, not: null },
        NOT: { id: { in: Array.from(await safetyExcludedForCall(practiceId, result.audioCutoff)) } },
      },
      select: { id: true, audioObjectKey: true },
    });
    for (const v of audioVisits) {
      if (!v.audioObjectKey) continue;
      try {
        await minio.removeObject(SCRIBE_BUCKET, v.audioObjectKey);
      } catch (err) {
        console.error(
          `[retention_purge] failed to delete ${v.audioObjectKey}:`,
          err instanceof Error ? err.message : err
        );
        continue;
      }
      // Null out the key so the row becomes "audio-purged" but
      // transcripts + outputs stay (retention windows differ).
      await prisma.scribeVisit.update({
        where: { id: v.id },
        data: { audioObjectKey: null },
      });
    }
  }

  // --- Transcripts + outputs ---
  if (result.transcriptCount > 0) {
    const visits = await prisma.scribeVisit.findMany({
      where: {
        practiceId,
        deletedAt: null,
        status: 'SIGNED',
        endedAt: { lt: result.transcriptCutoff, not: null },
        NOT: {
          id: { in: Array.from(await safetyExcludedForCall(practiceId, result.transcriptCutoff)) },
        },
      },
      select: { id: true },
    });
    const ids = visits.map((v: { id: string }) => v.id);
    if (ids.length > 0) {
      // Soft-delete visits so M6 audit + billing history remain resolvable.
      await prisma.scribeVisit.updateMany({
        where: { id: { in: ids } },
        data: { deletedAt: new Date() },
      });
    }
  }
}

/**
 * Cheap re-scan of safety-excluded visits at purge-execute time so a
 * race (clinician sets requires_immediate_follow_up between scan and
 * delete) can't ever flush a safety-sensitive row.
 */
async function safetyExcludedForCall(
  practiceId: string,
  cutoff: Date
): Promise<Set<string>> {
  const candidates = await prisma.scribeVisit.findMany({
    where: {
      practiceId,
      deletedAt: null,
      endedAt: { lt: cutoff, not: null },
    },
    select: { id: true },
  });
  const ids = candidates.map((v: { id: string }) => v.id);
  if (ids.length === 0) return new Set();
  const { findSafetyExcludedVisitIds } = await import('@/server/retention/query');
  return findSafetyExcludedVisitIds(prisma, ids);
}
