// ============================================================================
// Flesch-Kincaid Grade Level — client-side reading-level calculator
// ----------------------------------------------------------------------------
// User-added M4 addition (not in the spec). The patient-summary prompt
// targets 6th-grade reading level; this util gives the review UI live
// feedback so the clinician sees the grade level of any edits.
//
// Formula: FK = 0.39 * (words/sentences) + 11.8 * (syllables/words) - 15.59
//
// Syllable counting is heuristic (vowel-group + silent-e). Real clinical
// NLP would use cmudict; this is good enough to distinguish "5th grade"
// from "10th grade" with minimal client-side weight.
// ============================================================================

function countSyllables(word: string): number {
  const w = word.toLowerCase().replace(/[^a-z]/g, '');
  if (!w) return 0;
  // Strip a single silent e at end (but not for short words like "be").
  const stripped = w.length > 2 ? w.replace(/e$/, '') : w;
  const groups = stripped.match(/[aeiouy]+/g);
  return Math.max(1, groups?.length ?? 1);
}

export function fleschKincaidGrade(text: string): number {
  if (!text || !text.trim()) return 0;
  const sentences = Math.max(
    1,
    text.split(/[.!?]+/).filter((s) => s.trim().length > 0).length
  );
  const words = text.split(/\s+/).filter((w) => w.replace(/[^a-z]/gi, '').length > 0);
  if (words.length === 0) return 0;
  const syllables = words.reduce((sum, w) => sum + countSyllables(w), 0);
  const grade =
    0.39 * (words.length / sentences) +
    11.8 * (syllables / words.length) -
    15.59;
  return Math.max(0, Math.round(grade * 10) / 10);
}
