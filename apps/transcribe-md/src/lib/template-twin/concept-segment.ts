// ============================================================================
// THE ONE IDENTIFIER NORMALISER FOR CONCEPT SEGMENTS.
// ----------------------------------------------------------------------------
// Extracted from `encounter-facts/index.ts` so the L3 schema can apply the
// SAME normalisation the projector applies, rather than a second one that
// agrees today and drifts tomorrow.
//
// ⚠️ THE BYTES ARE COPIED, NOT RETYPED, AND THAT IS DELIBERATE. A normaliser
// that differs by one character re-opens the exact defect this move closes:
// the projector already turned `Heartburn` into `heartburn` when building
// `ros.gastrointestinal.heartburn`, while the L3 schema was rejecting the whole
// extraction for the capital letter. Two normalisers, one of them stricter, is
// how that asymmetry arose in the first place.
//
// A LEAF: it imports nothing, so anything may import it.
// ============================================================================

/**
 * NFKC, trimmed, lower-cased, non-alphanumerics folded to `_`, edge underscores
 * stripped, capped at 80 characters. An empty result becomes `unspecified` —
 * identifier normalisation only; it does not change the clinical meaning.
 */
export function conceptSegment(value: string): string {
  const segment = value
    .normalize('NFKC')
    .trim()
    .toLocaleLowerCase('en-US')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 80);
  return segment || 'unspecified';
}
