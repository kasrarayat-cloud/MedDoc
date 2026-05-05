// ============================================================================
// Audio confidence aggregator (Round 3 quality fix-pack Q0-5)
// ----------------------------------------------------------------------------
// Closes audit Findings 07.3 (Deepgram per-utterance confidence captured but
// not propagated) and 02.5 (heavy accent / mumbling produces overconfident
// SOAPs). Pure functions only — Layer 1 + Layer 1b call them after the
// Deepgram batch returns, the worker threads the result into L4/L5 input.
//
// The thresholds below are deliberately conservative. Deepgram nova-3-medical
// usually returns per-utterance confidence in the 0.85-0.99 band on clear
// English audio; values below 0.6 are the signal that the model was guessing
// (heavy accent, mumbling, background noise, sub-cardioid mic). The "should
// flag for review" rule fires when EITHER the median is bad (the audio is
// uniformly poor) OR more than 30% of utterances are individually low (the
// audio has rough patches the doctor needs to disambiguate).
// ============================================================================

/** Per-utterance Deepgram confidence below this is treated as "low". */
export const LOW_CONFIDENCE_THRESHOLD = 0.6;

/** Visit-level median below this triggers needsReview + L4/L5 hedge prompt. */
export const NEEDS_REVIEW_MEDIAN = 0.55;

/** Percent of utterances < threshold above this triggers needsReview +
 *  the L4/L5 hedge prompt. Expressed as 0-100 (not a fraction). */
export const NEEDS_REVIEW_LOW_CONF_PCT = 30;

export interface AudioConfidenceStats {
  /** Arithmetic mean across all utterances with a numeric confidence. */
  mean: number;
  /** Median (50th percentile). For even counts the average of the two
   *  middle values. */
  median: number;
  /** 10th percentile — the bottom-decile utterance. Surfaces the worst
   *  segments without being dragged around by a single outlier. */
  p10: number;
  /** Percent of utterances with confidence < threshold. 0-100 scale. */
  lowConfPct: number;
  /** Count of utterances with confidence < threshold. */
  lowConfCount: number;
  /** Count of utterances with a numeric confidence value (denominator
   *  for mean/median/p10/pct). */
  totalUtterances: number;
  /** Snapshot of LOW_CONFIDENCE_THRESHOLD at compute time. Persisted
   *  alongside the stats so that future threshold tuning doesn't make
   *  historical lowConfPct values incomparable. */
  threshold: number;
}

/**
 * Aggregate per-utterance Deepgram confidence into a single visit-level
 * record. Returns null when the input is empty OR contains no usable
 * confidence values — callers use null to mean "no audio confidence
 * signal available" (text_notes, single-block dictation, mocked runs).
 *
 * Utterances that lack a numeric `confidence` field are silently skipped;
 * if NONE survive the filter the function returns null.
 */
export function computeAudioConfidenceStats(
  utterances: ReadonlyArray<{ confidence?: number | null }>
): AudioConfidenceStats | null {
  if (!Array.isArray(utterances) || utterances.length === 0) return null;

  const confidences: number[] = [];
  for (const u of utterances) {
    const c = u.confidence;
    if (typeof c === 'number' && Number.isFinite(c)) confidences.push(c);
  }
  if (confidences.length === 0) return null;

  const sorted = [...confidences].sort((a, b) => a - b);
  const total = sorted.length;
  const sum = sorted.reduce((acc, v) => acc + v, 0);
  const mean = sum / total;
  const median =
    total % 2 === 1
      ? sorted[(total - 1) / 2]
      : (sorted[total / 2 - 1] + sorted[total / 2]) / 2;
  const p10 = percentile(sorted, 10);
  const lowConfCount = sorted.filter((v) => v < LOW_CONFIDENCE_THRESHOLD).length;
  const lowConfPct = (lowConfCount / total) * 100;

  return {
    mean,
    median,
    p10,
    lowConfPct,
    lowConfCount,
    totalUtterances: total,
    threshold: LOW_CONFIDENCE_THRESHOLD,
  };
}

/**
 * Visit-level decision: should the worker flip needsReview + ask L4/L5
 * to hedge? True when EITHER the median is below NEEDS_REVIEW_MEDIAN
 * (overall poor audio) OR more than NEEDS_REVIEW_LOW_CONF_PCT % of
 * utterances were individually low-confidence (rough patches).
 */
export function shouldFlagForReview(stats: AudioConfidenceStats): boolean {
  return (
    stats.median < NEEDS_REVIEW_MEDIAN ||
    stats.lowConfPct > NEEDS_REVIEW_LOW_CONF_PCT
  );
}

/** Percentile via linear interpolation between adjacent ranks. The
 *  input MUST be ascending-sorted. p is 0-100. */
function percentile(sorted: readonly number[], p: number): number {
  if (sorted.length === 0) return 0;
  if (sorted.length === 1) return sorted[0];
  const rank = (p / 100) * (sorted.length - 1);
  const lower = Math.floor(rank);
  const upper = Math.ceil(rank);
  if (lower === upper) return sorted[lower];
  const weight = rank - lower;
  return sorted[lower] * (1 - weight) + sorted[upper] * weight;
}
