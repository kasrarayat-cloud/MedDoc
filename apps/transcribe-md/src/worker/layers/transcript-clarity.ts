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
//   caught) vs the clear-speech cost. Measured marker rate on the noisiest
//   mixed-mono PriMock57 cases (WER 14-20%): 11-23 markers/case (~17 avg);
//   clean prod audio is estimated at ~2-6/visit (audit 2026-06-11).
//   Adjacent marked words merge into ONE marker, and an OPEN run absorbs
//   ANY adjacent sub-threshold word (stopwords included) — the stopword/
//   length filter gates run INITIATION only, so a low-confidence "no"
//   inside garble can't be emitted as a confident fragment ("phantom
//   negation", audit WARN-3). Digit-bearing tokens (doses, vitals, B12)
//   are ALWAYS content words (audit WARN-1).
//
// DELIBERATE TRADE-OFF (audit WARN-4): negation/laterality function words
// ("no", "not", "yes", "right") stay in the stopword set — their discourse
// frequency would flood markers if they could INITIATE runs. The risk that
// remains: a STANDALONE low-confidence negation before clear content
// ("no(0.4) chest(0.9) pain") stays asserted. Accepted: marking can never
// flip a negation (the marked-object direction is safe), and run-absorption
// covers the inside-garble case.
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

/** Below the confidence threshold at all? (run-ABSORPTION criterion —
 *  stopwords and short tokens included, audit WARN-3). */
function isLowConfidence(w: DeepgramWord): boolean {
  return typeof w.confidence === 'number' && w.confidence < UNCLEAR_WORD_CONFIDENCE;
}

/** May this word INITIATE a marked run? Content words only — but any token
 *  carrying a digit (doses, vitals, "b12") is always content (audit WARN-1:
 *  the letters-only strip used to exempt a 0.32-confidence dose numeral). */
function isMarkable(w: DeepgramWord): boolean {
  if (!isLowConfidence(w)) return false;
  if (/\d/.test(w.word ?? '')) return true; // digit-bearing = always content
  const raw = (w.word ?? '').toLowerCase().replace(/[^a-z']/g, '');
  if (raw.length < 3) return false; // 1-2 letter tokens are function noise
  if (CLARITY_STOPWORDS.has(raw)) return false;
  return true;
}

/** Trailing sentence punctuation of a word, so a marked run keeps its
 *  sentence boundary (audit NIT-3: "called sphenitol. Take it" must not
 *  merge sentences when the drug name is marked). */
function trailingPunct(w: DeepgramWord): string {
  const p = (w.punctuated_word ?? '').trim();
  const m = p.match(/[.?!,]$/);
  return m ? m[0] : '';
}

/**
 * Rebuild an utterance's text from its word stream with low-confidence
 * content-word runs replaced by the `[unclear in recording]` marker.
 * Pure + deterministic. Returns `u.transcript` untouched when no
 * word-level data is available OR nothing is markable (strictly additive:
 * zero-marker utterances stay byte-identical to the raw transcript —
 * audit NIT-2).
 */
export function markUnclearTranscript(u: DeepgramUtterance): string {
  const words = Array.isArray(u.words) ? u.words : [];
  if (words.length === 0) return (u.transcript ?? '').trim();
  if (!words.some(isMarkable)) return (u.transcript ?? '').trim();

  const out: string[] = [];
  let inMarkedRun = false;
  let runPunct = '';
  const closeRun = () => {
    if (inMarkedRun && runPunct) {
      // restore the sentence boundary the marked run swallowed
      out[out.length - 1] = `${UNCLEAR_MARKER}${runPunct}`;
    }
    inMarkedRun = false;
    runPunct = '';
  };
  for (const w of words) {
    // An OPEN run absorbs ANY sub-threshold word (stopwords included) —
    // a 0.31-confidence "no" between garble must not surface as confident
    // text (audit WARN-3 "phantom negation"). Initiation stays content-only.
    if (isMarkable(w) || (inMarkedRun && isLowConfidence(w))) {
      if (!inMarkedRun) {
        out.push(UNCLEAR_MARKER);
        inMarkedRun = true;
      }
      runPunct = trailingPunct(w) || runPunct;
      continue;
    }
    closeRun();
    out.push((w.punctuated_word ?? w.word ?? '').trim());
  }
  closeRun();
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
