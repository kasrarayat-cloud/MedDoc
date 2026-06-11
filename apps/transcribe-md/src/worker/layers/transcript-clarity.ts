// ============================================================================
// Transcript clarity — deterministic unclear-span marking (2026-06-11,
// L4 inaudible-span hardening; hallucination-reconciliation follow-up).
// ----------------------------------------------------------------------------
// THE DEFECT THIS CLOSES: Deepgram garbles unintelligible audio into
// plausible-looking words at LOW word confidence, and the pipeline asserted
// them as fact — measured on PriMock57: an inaudible drug name became
// "sphenitol" (conf 0.61) and shipped in the note's plan; "fat pup"
// (0.38/0.51) became a named restaurant; "trabalotza" (0.64) is pure garble.
// The models can't hedge spans they can't see — the visit-level confidence
// hedge (audio-confidence.ts) only fires when the WHOLE recording is bad.
//
// MECHANISM (pure, unit-tested): rebuild each utterance's text from its
// word stream, replacing runs of low-confidence CONTENT words with the
// product's established marker `[unclear in recording]`. Stopword dips are
// NOT marked — calibration on PriMock57 mixed audio showed the sub-0.65
// population is dominated by harmless function-word dips ("okay:0.64",
// "or:0.53") which no clinical claim rests on; marking them would flood the
// transcript (~30-40 markers/visit) and train the models to ignore markers.
//
// THRESHOLD (documented per the hardening spec):
//   UNCLEAR_WORD_CONFIDENCE = 0.65 — chosen from measured garble
//   (sphenitol 0.61, trabalotza 0.64, pup 0.48-0.51, sedative 0.48 all
//   caught) vs the clear-speech cost (content words <0.65 on the noisiest
//   mixed-mono PriMock57 cases ≈ 8-15/visit; far fewer on clean prod audio).
//   Adjacent marked words merge into ONE marker.
//
// DEGRADES SAFELY: utterances without word-level data (the dictation path
// runs Deepgram with utterances disabled; legacy rows) pass through
// unchanged — marking is an additive guard, never a gate.
//
// SCOPE: affects ONLY the role-labeled transcript fed to the model layers
// (L3/L4/L5). The Transcript tab renders raw utterances separately and is
// untouched.
// ============================================================================

import type { DeepgramUtterance, DeepgramWord } from '@meddoc/ai';

export const UNCLEAR_WORD_CONFIDENCE = 0.65;
export const UNCLEAR_MARKER = '[unclear in recording]';

/** Function words whose routine confidence dips carry no clinical content —
 *  never marked. Lowercase, compared against the raw `word` field. */
const CLARITY_STOPWORDS = new Set([
  'a', 'an', 'and', 'are', 'as', 'at', 'be', 'but', 'by', 'do', 'does',
  'for', 'from', 'had', 'has', 'have', 'he', 'her', 'his', 'i', 'if', 'in',
  'is', 'it', "it's", 'its', 'just', 'like', 'me', 'my', 'no', 'not', 'of',
  'oh', 'okay', 'on', 'or', 'our', 'she', 'so', 'that', 'the', 'their',
  'them', 'then', 'there', 'they', 'this', 'to', 'um', 'uh', 'was', 'we',
  'were', 'what', 'when', 'which', 'who', 'will', 'with', 'would', 'yeah',
  'yes', 'you', 'your', 'mhmm', 'hmm', 'right',
]);

function isMarkable(w: DeepgramWord): boolean {
  if (typeof w.confidence !== 'number' || w.confidence >= UNCLEAR_WORD_CONFIDENCE) {
    return false;
  }
  const raw = (w.word ?? '').toLowerCase().replace(/[^a-z']/g, '');
  if (raw.length < 3) return false; // 1-2 letter tokens are function noise
  if (CLARITY_STOPWORDS.has(raw)) return false;
  return true;
}

/**
 * Rebuild an utterance's text from its word stream with low-confidence
 * content-word runs replaced by the `[unclear in recording]` marker.
 * Pure + deterministic. Returns `u.transcript` untouched when no
 * word-level data is available (additive guard, never a gate).
 */
export function markUnclearTranscript(u: DeepgramUtterance): string {
  const words = Array.isArray(u.words) ? u.words : [];
  if (words.length === 0) return (u.transcript ?? '').trim();

  const out: string[] = [];
  let inMarkedRun = false;
  for (const w of words) {
    if (isMarkable(w)) {
      if (!inMarkedRun) {
        out.push(UNCLEAR_MARKER);
        inMarkedRun = true;
      }
      // adjacent low-confidence words collapse into the open marker
      continue;
    }
    inMarkedRun = false;
    out.push((w.punctuated_word ?? w.word ?? '').trim());
  }
  const text = out.filter(Boolean).join(' ').trim();
  // Word stream empty after filtering (defensive) → fall back to raw text.
  return text.length > 0 ? text : (u.transcript ?? '').trim();
}

/** True when any utterance produced at least one marker — lets callers log
 *  marker telemetry without re-deriving. */
export function countUnclearMarkers(text: string): number {
  let n = 0;
  let i = 0;
  for (;;) {
    const at = text.indexOf(UNCLEAR_MARKER, i);
    if (at === -1) return n;
    n += 1;
    i = at + UNCLEAR_MARKER.length;
  }
}
