// ============================================================================
// Cache for the visit-document preview — preview-side ONLY.
// ----------------------------------------------------------------------------
// Every preview is a full fill: a MinIO source read, the resolver, the bridge,
// a DOCX render with round-trip verification, then up to twelve seconds of
// LibreOffice. That is fine once. It is not fine on every mount and every
// adopt, and phase 2 shipped with no cache at all.
//
// THE KEY IS THE NOTE'S VERSION. `soapVersion` is bumped by every path that can
// change what the document says — adopting a suggestion, a doctor's edit — so a
// stale entry cannot survive a change to the note. Signing is covered too: the
// signed view reads the STORED delivered bytes, never this.
//
// WHAT THIS DOES NOT TOUCH: the fill manifest, the artifact store, the sign
// gate. Nothing here is ever read by the signing path — the gate still
// validates the stored manifest exactly as it did before this file existed. A
// cache that could feed a signature would be a completely different object with
// completely different rules; this one only decides whether we re-render a
// picture we already rendered.
//
// It is also entirely optional. Redis down or cold → we do the work again.
// ============================================================================

import { getRedis, isRedisReady } from '@/lib/redis';

/** Long enough to cover a review session, short enough that nothing lingers. */
const TTL_SECONDS = 30 * 60;

/** Over this we decline to cache rather than push a multi-megabyte blob into a
 *  128 MB instance with no eviction policy — the job broker going down with an
 *  OOM would cost far more than re-rendering a preview. */
const MAX_CACHED_BYTES = 1_500_000;

/** THE CACHED VALUE IS PHI — a rendered PDF of a patient's clinical form.
 *
 *  It is NOT "the same posture as the queue payloads already there": those
 *  carry `{ visitId, userId }` and no clinical content. This is the first PHI
 *  at rest in Redis, and Redis runs with `--appendonly yes`, so an entry also
 *  lands in the AOF and outlives its TTL until the next rewrite.
 *
 *  Two bounds follow from that, both enforced below:
 *    • a hard SIZE ceiling — over it we simply do not cache
 *    • ONE entry per visit — a write drops the visit's other versions first,
 *      so a long review session cannot accumulate a megabyte per adopt in the
 *      128 MB instance that also brokers the clinical pipeline. */
/** The rendering VARIANT is part of the identity.
 *
 *  Without it, a styled entry written before certification was served to the
 *  twin path afterwards: the doctor uploaded and certified their own form and
 *  kept being shown QuillMD's layout for the rest of the TTL, silently. */
export type FillVariant = 'twin' | 'styled';

/** ⚠️ THE VERSION PREFIX IS BUMPED WHENEVER THE BUILDER'S OUTPUT CHANGES, AND
 *  THAT IS NOT AUTOMATIC — the key holds the visit, the variant and the
 *  `soapVersion`, but NOTHING that identifies the RENDERER. So a deploy that
 *  changes what the same note renders to leaves entries that are still
 *  "current" by every term in the key.
 *
 *  `v2 -> v3` for the numbered-list fidelity fix: for up to the TTL after that
 *  deploy, a doctor reloading the pre-sign canvas would have been served the
 *  PRE-FIX bytes — RECOMMENDATIONS 4/5/6 — while `…/export/docx` and
 *  `…/export/pdf` both returned the corrected 1/2/3. Two surfaces that agreed
 *  before the deploy would have disagreed for thirty minutes, on the surface
 *  the doctor actually reads.
 *
 *  ⚠️ AND BOTH OCCURRENCES MOVE TOGETHER. `invalidateVisitFills` SCANs on this
 *  same prefix, so bumping only the writer would leave it scanning for `v2`
 *  keys while new `v3` keys accumulate — quietly breaking the one-entry-per-
 *  visit bound that exists because THE CACHED VALUE IS PHI. */
function key(visitId: string, soapVersion: number, variant: FillVariant): string {
  return `visitdoc:v3:${variant}:${visitId}:${soapVersion}`;
}

export interface CachedFill {
  kind: 'pdf' | 'docx_fallback';
  /** base64 */
  data: string;
  counts: { filled: number; needsReview: number; notMentioned: number } | null;
  fillSha: string;
  /** The named reason the PDF path was missed, when it was. */
  reason: string | null;
}

export async function readCachedFill(
  visitId: string,
  soapVersion: number,
  variant: FillVariant,
): Promise<CachedFill | null> {
  if (!isRedisReady()) return null;
  try {
    const raw = await getRedis().get(key(visitId, soapVersion, variant));
    return raw ? (JSON.parse(raw) as CachedFill) : null;
  } catch {
    // A cache miss and a broken cache are the same thing to the caller.
    return null;
  }
}

/**
 * Drop every cached fill for a visit.
 *
 * Strictly speaking the version key already makes stale entries unreachable —
 * this is for the cases where that reasoning could be wrong: a rollback of
 * soapVersion, or a fill whose inputs changed without the note changing. The
 * cost of an unnecessary invalidation is one re-render; the cost of a missed
 * one is a doctor reading a document that is not theirs any more.
 */
export async function invalidateVisitFills(visitId: string): Promise<void> {
  if (!isRedisReady()) return;
  try {
    const redis = getRedis();
    // SCAN, not KEYS: this runs on the request path of a shared Redis.
    let cursor = '0';
    do {
      const [next, found] = await redis.scan(
        cursor,
        'MATCH',
        `visitdoc:v3:*:${visitId}:*`,
        'COUNT',
        100,
      );
      cursor = next;
      if (found.length) await redis.del(...found);
    } while (cursor !== '0');
  } catch {
    // Best effort — the version in the key is the real guarantee.
  }
}

export async function writeCachedFill(
  visitId: string,
  soapVersion: number,
  value: CachedFill,
  variant: FillVariant,
): Promise<void> {
  // A cache that never stores anything is indistinguishable from one that is
  // working, because everything still renders — just slowly. Say which it is.
  if (!isRedisReady()) {
    console.info(`[visitdoc-cache] skipped write for ${visitId}: redis not ready`);
    return;
  }
  const k = key(visitId, soapVersion, variant);
  const payload = JSON.stringify(value);
  if (payload.length > MAX_CACHED_BYTES) {
    console.info(
      `[visitdoc-cache] not caching ${visitId}: ${payload.length}B over the ceiling`,
    );
    return;
  }
  try {
    // ONE entry per visit: drop the older versions before writing the new one.
    await invalidateVisitFills(visitId);
    await getRedis().set(k, payload, 'EX', TTL_SECONDS);
  } catch (err) {
    const cls = err instanceof Error ? err.constructor.name : 'Unknown';
    console.warn(`[visitdoc-cache] write failed for ${visitId} (${cls}); preview unaffected`);
  }
}

