// ============================================================================
// Retention — pure query helpers (M7)
// ----------------------------------------------------------------------------
// One practice at a time, finds ScribeVisit rows that are past each of
// the two retention windows:
//   - audio:      endedAt older than (now - audioRetentionDays), visit
//                 still has an audioObjectKey
//   - transcript: endedAt older than (now - transcriptRetentionDays), visit
//                 is SIGNED (never purge unsigned/processing visits)
//
// A SOAP output with requires_immediate_follow_up: true NEVER gets
// purged — safety-sensitive visits (M5 psychiatry cases) stay until a
// clinician reviews them (M7 D8 addition).
// ============================================================================

import type { PrismaClient } from '@prisma/client';
import { SoapNoteSchema } from '@meddoc/types';

export interface RetentionPolicy {
  audioRetentionDays: number;
  transcriptRetentionDays: number;
}

export interface RetentionScanResult {
  practiceId: string;
  policy: RetentionPolicy;
  audioCount: number;
  /** Sample audio object keys (up to 5) so logs give ops a concrete anchor. */
  audioSample: string[];
  transcriptCount: number;
  /** Sample ScribeVisit ids (up to 5). */
  transcriptSample: string[];
  /** Visits excluded because of the SAFETY guardrail. */
  safetyExcludedCount: number;
  /** Oldest endedAt in the transcript-purge set (ISO). */
  oldestSignedAt: string | null;
  /** The wall-clock cutoff dates used for the scan. */
  audioCutoff: Date;
  transcriptCutoff: Date;
}

function daysAgo(days: number, now: Date = new Date()): Date {
  return new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
}

/**
 * Inspect the latest SOAP ScribeOutput for any visit id in `visitIds`
 * and return the subset that carry requires_immediate_follow_up: true.
 * Those visits are the "safety-excluded" set.
 */
export async function findSafetyExcludedVisitIds(
  prisma: PrismaClient,
  visitIds: string[]
): Promise<Set<string>> {
  if (visitIds.length === 0) return new Set();
  const rows = await prisma.scribeOutput.findMany({
    where: { visitId: { in: visitIds }, type: 'SOAP' },
    select: { visitId: true, content: true, createdAt: true },
    orderBy: { createdAt: 'desc' },
  });
  // Keep only the newest SOAP per visit (rows ordered desc).
  const latestByVisit = new Map<string, unknown>();
  for (const r of rows) {
    if (!latestByVisit.has(r.visitId)) latestByVisit.set(r.visitId, r.content);
  }
  const excluded = new Set<string>();
  for (const [visitId, content] of latestByVisit) {
    const parsed = SoapNoteSchema.safeParse(content);
    if (parsed.success && parsed.data.requires_immediate_follow_up === true) {
      excluded.add(visitId);
    }
  }
  return excluded;
}

/**
 * Run a retention scan for a single practice. Does NOT mutate anything
 * — caller decides whether to purge based on RETENTION_PURGE_LIVE.
 */
export async function scanPracticeRetention(
  prisma: PrismaClient,
  practiceId: string,
  policy: RetentionPolicy,
  now: Date = new Date()
): Promise<RetentionScanResult> {
  const audioCutoff = daysAgo(policy.audioRetentionDays, now);
  const transcriptCutoff = daysAgo(policy.transcriptRetentionDays, now);

  // --- Audio candidates: visits with audio still present past cutoff ---
  const audioCandidates = await prisma.scribeVisit.findMany({
    where: {
      practiceId,
      deletedAt: null,
      audioObjectKey: { not: null },
      endedAt: { lt: audioCutoff, not: null },
    },
    select: { id: true, audioObjectKey: true, endedAt: true },
  });

  // --- Transcript candidates: SIGNED visits past transcript cutoff ---
  const transcriptCandidates = await prisma.scribeVisit.findMany({
    where: {
      practiceId,
      deletedAt: null,
      status: 'SIGNED',
      endedAt: { lt: transcriptCutoff, not: null },
    },
    select: { id: true, endedAt: true },
    orderBy: { endedAt: 'asc' },
  });

  // Safety exclusion on the UNION of candidates so a psychiatry visit
  // never slips through either cutoff.
  const allCandidateIds = Array.from(
    new Set([...audioCandidates.map((v) => v.id), ...transcriptCandidates.map((v) => v.id)])
  );
  const safetyExcluded = await findSafetyExcludedVisitIds(prisma, allCandidateIds);

  const audioAfterSafety = audioCandidates.filter((v) => !safetyExcluded.has(v.id));
  const transcriptAfterSafety = transcriptCandidates.filter(
    (v) => !safetyExcluded.has(v.id)
  );

  return {
    practiceId,
    policy,
    audioCount: audioAfterSafety.length,
    audioSample: audioAfterSafety
      .slice(0, 5)
      .map((v) => v.audioObjectKey)
      .filter((s): s is string => !!s),
    transcriptCount: transcriptAfterSafety.length,
    transcriptSample: transcriptAfterSafety.slice(0, 5).map((v) => v.id),
    safetyExcludedCount: safetyExcluded.size,
    oldestSignedAt:
      transcriptAfterSafety[0]?.endedAt?.toISOString() ?? null,
    audioCutoff,
    transcriptCutoff,
  };
}
