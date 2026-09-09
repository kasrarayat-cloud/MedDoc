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
// stale entry cannot survive a change to the note.
//
// ⚠️ THIS USED TO SAY "Signing is covered too: the signed view reads the STORED
// delivered bytes, never this." THAT IS FALSE IN PRODUCTION, and was corrected
// under ruling #115 by the session that had to reason about it.
//
// It is true only where a CERTIFIED twin has produced stored native bytes.
// Production holds ZERO compiled twin versions and ZERO fill manifests
// (measured 2026-08-15, 27 signed visits), so `loadNativeTemplateDocxForVisit`
// returns null for every one of them and the signed view re-derives through the
// SAME `styledDocument` -> `loadVisitExportData` -> `generateVisitDocx` path the
// pre-sign preview uses — and reads THIS cache on the way. So a renderer change
// reaches the signed view too, which is exactly why the prefix below is bumped
// on one. The sentence was true when written, about code somewhere else; that
// is the whole failure mode of a comment asserting another module's behaviour.
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
 *  `v3 -> v4` for ruling #115, the visit-date fix, and it is the SAME shape a
 *  second time: the "Visit date" row moves from `signedAt` to `createdAt`, so
 *  the same note at the same `soapVersion` renders different bytes. Without the
 *  bump a doctor reloading the canvas within the TTL would read the SIGNING
 *  date while the Word and PDF exports read the encounter date — and the visit
 *  most likely to be reloaded right after signing is precisely the one whose
 *  two dates differ. ⚠️ The key still names nothing about the renderer, so this
 *  will need doing again; it is not automatic and no test can infer it.
 *
 *  `v4 -> v5` for ruling #117, the attestation footer, and it is the SAME shape
 *  a THIRD time — this time found by an adversarial pass rather than by its
 *  author, which is the reason the sentence above ("this will need doing again;
 *  it is not automatic and no test can infer it") is worth its space. The
 *  unsigned export gains `DRAFT — Not yet signed.` in a section footer on every
 *  page, so the same note at the same `soapVersion` renders different bytes.
 *  ⚠️ WITHOUT THE BUMP THE DEFECT INVERTS ITSELF ONTO THE ONE SURFACE #117 WAS
 *  WRITTEN FOR: for up to the TTL, a doctor reloading the pre-sign canvas is
 *  served the PRE-FOOTER bytes — pages 1..n-1 indistinguishable from a finished
 *  record — while `…/export/docx` returns the marked file. The canvas is the
 *  surface she actually reads before signing.
 *
 *  ⚠️ BOTH OCCURRENCES MOVE TOGETHER — and this comment was NOT ENOUGH. On the
 *  `v4 -> v5` bump the writer moved and the SCAN did not; it was caught by a
 *  sweep AFTER the commit message had already claimed both had moved. Bumping
 *  only the writer leaves `invalidateVisitFills` scanning for the OLD version
 *  while new keys accumulate — quietly breaking the one-entry-per-visit bound
 *  that exists because THE CACHED VALUE IS PHI.
 *
 *  ⚠️ SO THE VERSION IS NOW ONE CONSTANT AND THE DIVERGENCE IS UNREPRESENTABLE.
 *  A warning that has to be obeyed by hand is obeyed until somebody is tired;
 *  there is nothing to keep in step here any more. Bump `KEY_VERSION`, and the
 *  writer and the SCAN move by construction. */
// ⚠️ v6 — REVIEW-DEFAULTS widened `CachedFill` with `insertableDefaults`.
// A pre-deploy v5 entry carries none, and the panel treats an absent list as
// "we did not compute it" and renders NOTHING — so every visit with a warm
// cache would silently have no "Your blanks" panel until its note changed.
// Found by an adversarial pass; the shape changed and the key did not.
//
// ⚠️ v7 — OWNER RULING #203, AND IT IS v6's TRAP ONE STEP SUBTLER. The #1018
// fix changes WHICH FIELDS `insertableDefaults` CONTAINS without changing its
// SHAPE: the offer is withdrawn on the per-visit `reasonCode` instead of the
// mapping's static policy. A warm v6 entry therefore deserialises perfectly and
// serves the PRE-FIX offer list — the one that offers a default on every omit
// field — for up to the 30-minute TTL after deploy. Nothing would look wrong.
//
// v6's own comment says "the shape changed and the key did not". This is
// **the CONTENTS changed and the key did not**, which no schema check can see.
// FOURTH instance of this class in this file; the three above are its record.
const KEY_VERSION = 'v7';

function key(visitId: string, soapVersion: number, variant: FillVariant): string {
  return `visitdoc:${KEY_VERSION}:${variant}:${visitId}:${soapVersion}`;
}

export interface CachedFill {
  kind: 'pdf' | 'docx_fallback';
  /** base64 */
  data: string;
  counts: {
    filled: number;
    needsReview: number;
    notMentioned: number;
  } | null;
  /** REVIEW-DEFAULTS item 1 — the blank scaffolded controls this fill found a
   *  doctor default for. OPTIONAL, because an entry cached before this field
   *  existed carries none and `undefined` is the honest answer: *we did not
   *  compute it*, which is different from *there are none*. The surface renders
   *  nothing rather than an empty panel. */
  insertableDefaults?: {
    fieldId: string;
    label: string;
    scaffoldText: string;
    inserted: boolean;
  }[] | null;
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
        // Same constant as the writer — see KEY_VERSION. These cannot diverge.
        `visitdoc:${KEY_VERSION}:*:${visitId}:*`,
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

