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
//
// 2026-05-13 extension (Step 2 of post-cross-input-mode-audit fix matrix,
// closes Finding 2): the helper now ALSO detects the "model returned
// status:ok with codes:[] / em:none" shape. PR #232's UC2 audio_upload
// scenario surfaced this — L7a completed without throwing but emitted
// an empty codes array. Pre-extension G9 didn't catch this because
// status:ok masks the empty output. The helper now accepts an
// optional `outputs` parameter carrying the L7a + L7b results; when
// the output is empty despite status:ok the helper flags it with a
// distinct EMPTY label so audit-log forensics can separate "the layer
// crashed" from "the model returned nothing."
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

/** Output shapes the helper inspects to catch "empty result with
 *  status:ok" cases. Both shapes are optional — call sites that don't
 *  yet pass them keep the historic failed-only detection behavior. */
export interface IcdLikeResult {
  codes?: ReadonlyArray<unknown>;
}
export interface CptLikeResult {
  em?: { code?: string | null } | null;
  procedures?: ReadonlyArray<unknown>;
}

export interface LayerOutputs {
  icdCodes?: IcdLikeResult | null;
  cptCodes?: CptLikeResult | null;
}

/** Distinguishes "the layer crashed" from "the layer returned nothing
 *  successfully." Both flip needsReview, but the audit-log metadata
 *  uses the discriminator so admin forensics can grep separately. */
export type IncompleteCause = 'failed' | 'empty';

export interface IncompleteAutomationResult {
  /** True iff at least one load-bearing layer failed OR returned empty. */
  needsReview: boolean;
  /** Doctor-facing one-line reason; null when nothing tripped. Capped
   *  at 500 chars so a verbose stack trace can't blow past Postgres
   *  TEXT-row sane sizes. */
  reviewReason: string | null;
  /** Which load-bearing layers tripped (subset of LOAD_BEARING_L7_TASKS).
   *  Empty when nothing tripped. */
  failedLayers: LoadBearingTaskKey[];
  /** Per-tripped-layer reason strings, mirror of `reviewReason` but
   *  structured for the audit-log row's metadata field. Each value
   *  truncated to 300 chars. */
  reasonsByLayer: Record<LoadBearingTaskKey, string | null>;
  /** Per-tripped-layer cause discriminator. Helps the audit-log row
   *  separate genuine crashes ('failed') from "model returned nothing
   *  successfully" ('empty'). */
  causeByLayer: Record<LoadBearingTaskKey, IncompleteCause | null>;
}

/** Inspect a confidenceScores roll-up + (optionally) the L7a/L7b
 *  output columns. Reports whether the visit needs review because a
 *  load-bearing L7 task errored OR returned empty.
 *
 *  Backwards-compatible: existing callers that pass only `scores`
 *  keep the historic failed-only detection. Callers that pass
 *  `outputs` get the additional empty-codes detection (closes the
 *  PR #232 Finding 2 / UC2 audio_upload anomaly). */
export function detectIncompleteAutomation(
  scores: AutomationConfidenceScores | null | undefined,
  outputs?: LayerOutputs,
): IncompleteAutomationResult {
  const tripped: LoadBearingTaskKey[] = [];
  const reasonsByLayer: Record<LoadBearingTaskKey, string | null> = {
    icd_coding: null,
    cpt_coding: null,
    rx_drafting: null,
  };
  const causeByLayer: Record<LoadBearingTaskKey, IncompleteCause | null> = {
    icd_coding: null,
    cpt_coding: null,
    rx_drafting: null,
  };

  // Pass 1: scores → 'failed' detection (the original G9 behavior).
  if (scores) {
    for (const key of LOAD_BEARING_L7_TASKS) {
      const entry = scores[key];
      if (entry && entry.status === 'failed') {
        tripped.push(key);
        reasonsByLayer[key] = entry.reason?.slice(0, 300) ?? 'unknown';
        causeByLayer[key] = 'failed';
      }
    }
  }

  // Pass 2: outputs → 'empty' detection. Only inspects layers that
  // weren't ALREADY counted as 'failed' (a failed layer's empty output
  // is a known consequence, not a distinct signal). Only inspects
  // load-bearing layers icd_coding + cpt_coding — rx_drafting is
  // intentionally excluded because many visits legitimately carry no
  // Rx (e.g. derm-biopsy follow-up, screening encounters).
  if (outputs) {
    if (causeByLayer.icd_coding == null && isIcdEmpty(outputs.icdCodes)) {
      tripped.push('icd_coding');
      reasonsByLayer.icd_coding = 'returned empty codes array (status:ok)';
      causeByLayer.icd_coding = 'empty';
    }
    if (causeByLayer.cpt_coding == null && isCptEmpty(outputs.cptCodes)) {
      tripped.push('cpt_coding');
      reasonsByLayer.cpt_coding = 'no E&M code emitted (status:ok)';
      causeByLayer.cpt_coding = 'empty';
    }
  }

  if (tripped.length === 0) {
    return {
      needsReview: false,
      reviewReason: null,
      failedLayers: [],
      reasonsByLayer,
      causeByLayer,
    };
  }

  const perLayer = tripped.map((k) => {
    const reason = reasonsByLayer[k] ?? 'unknown';
    return `${k.replace('_', '-')}: ${reason}`;
  });
  const joined = perLayer.join('; ').slice(0, 500);
  return {
    needsReview: true,
    reviewReason: `Auto-coding incomplete — ${joined}. Click Retry to reprocess.`,
    failedLayers: tripped,
    reasonsByLayer,
    causeByLayer,
  };
}

/** Empty when the column is null or codes is missing / not an array /
 *  zero-length. */
function isIcdEmpty(icd: IcdLikeResult | null | undefined): boolean {
  if (icd == null) return true;
  const codes = icd.codes;
  if (!Array.isArray(codes)) return true;
  return codes.length === 0;
}

/** Empty when the column is null or no E&M code was emitted. Procedures
 *  + modifiers being empty does NOT trip the rule — many established-
 *  patient visits legitimately bill only the E&M tier. */
function isCptEmpty(cpt: CptLikeResult | null | undefined): boolean {
  if (cpt == null) return true;
  const em = cpt.em;
  if (em == null) return true;
  const code = em.code;
  return typeof code !== 'string' || code.trim() === '';
}
