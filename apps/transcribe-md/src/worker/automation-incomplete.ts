// ============================================================================
// Deep-audit G9 helper — detect a partial L7 failure that should flip
// needsReview + populate a reviewReason for the doctor.
// ----------------------------------------------------------------------------
// The worker's L7 fan-out (worker.ts) runs five tasks via
// Promise.allSettled and rolls per-task outcomes into a
// `confidenceScores` shape:
//
//   {
//     icd_coding:      { status: 'ok' | 'failed' | 'skipped'; reason?: string },
//     cpt_coding:      { status: 'ok' | 'failed' | 'skipped'; reason?: string },
//     rx_drafting:     { status: 'ok' | 'failed' | 'skipped'; reason?: string },
//     referrals:       { ... },
//     patient_summary: { ... },
//   }
//
// Pre-fix, the worker transitioned to status=READY regardless of which
// tasks failed. The doctor would open the visit and see a SOAP with
// empty codes/Rx columns and no banner indicating partial completion.
// Deep-audit G9 documents the demo-blocking scenario where Anthropic
// credit exhaustion mid-pipeline left V3 in this state.
//
// The fix: when ANY of the THREE load-bearing layers (icd-coding /
// cpt-coding / rx-drafting) fails, flip needsReview + populate
// reviewReason so the visit surfaces in the review queue with a
// specific reason + retry CTA. Status stays READY because the SOAP
// itself is valid; the T-M6 design choice (one layer's failure doesn't
// fail the visit) is preserved.
//
// 7d (referrals) and 7e (patient summary) are NOT load-bearing — they
// augment the visit page but the doctor doesn't need them to sign the
// SOAP. Their failures roll up into confidenceScores only.
// ============================================================================

/** Per-layer outcome shape written into `confidenceScores` by the
 *  worker's L7 fan-out roll-up. Mirrors the inline shape in
 *  apps/transcribe-md/src/worker.ts:775-779. */
export type LayerStatus =
  | { status: 'ok'; metadata?: unknown }
  | { status: 'skipped' }
  | { status: 'failed'; reason: string };

export type AutomationConfidenceScores = Record<string, LayerStatus>;

/** Load-bearing tasks — failure of any of these flips needsReview.
 *  Order matters for `reviewReason` readability (icd → cpt → rx). */
export const LOAD_BEARING_L7_TASKS = [
  'icd_coding',
  'cpt_coding',
  'rx_drafting',
] as const;

export type LoadBearingTaskKey = (typeof LOAD_BEARING_L7_TASKS)[number];

export interface IncompleteAutomationResult {
  /** True iff at least one load-bearing layer failed. */
  needsReview: boolean;
  /** Doctor-facing one-line reason; null when nothing failed. Capped
   *  at 500 chars so a verbose stack trace can't blow past Postgres
   *  TEXT-row sane sizes. */
  reviewReason: string | null;
  /** Which load-bearing layers failed (subset of LOAD_BEARING_L7_TASKS).
   *  Empty when nothing failed. */
  failedLayers: LoadBearingTaskKey[];
  /** Per-failed-layer reason strings, mirror of `reviewReason` but
   *  structured for the audit-log row's metadata field. Each value
   *  truncated to 300 chars. */
  reasonsByLayer: Record<LoadBearingTaskKey, string | null>;
}

/** Inspect a confidenceScores roll-up + report whether the visit
 *  needs review because a load-bearing L7 task errored. */
export function detectIncompleteAutomation(
  scores: AutomationConfidenceScores | null | undefined,
): IncompleteAutomationResult {
  const failed: LoadBearingTaskKey[] = [];
  const reasonsByLayer: Record<LoadBearingTaskKey, string | null> = {
    icd_coding: null,
    cpt_coding: null,
    rx_drafting: null,
  };

  if (scores) {
    for (const key of LOAD_BEARING_L7_TASKS) {
      const entry = scores[key];
      if (entry && entry.status === 'failed') {
        failed.push(key);
        reasonsByLayer[key] = entry.reason?.slice(0, 300) ?? 'unknown';
      }
    }
  }

  if (failed.length === 0) {
    return {
      needsReview: false,
      reviewReason: null,
      failedLayers: [],
      reasonsByLayer,
    };
  }

  const perLayer = failed.map((k) => {
    const e = scores?.[k];
    const reason = e?.status === 'failed' ? e.reason : 'unknown';
    return `${k.replace('_', '-')}: ${reason}`;
  });
  const joined = perLayer.join('; ').slice(0, 500);
  return {
    needsReview: true,
    reviewReason: `Auto-coding incomplete — ${joined}. Click Retry to reprocess.`,
    failedLayers: failed,
    reasonsByLayer,
  };
}
