// ============================================================================
// Flesch-Kincaid grade level (T-M6)
// ----------------------------------------------------------------------------
// Used by Layer 7e to check whether the generated patient summary is at
// or below an 8th-grade reading level. No dependency — the standard
// formula + a decent syllable heuristic is ~40 lines of TypeScript.
//
//   grade = 0.39*(words/sentences) + 11.8*(syllables/words) - 15.59
// ============================================================================

// Rough abbreviation list — tokens ending in "." we should NOT treat as
// sentence terminators. Conservative so we don't miss real sentences; the
// list covers common clinical/English cases.
const ABBREVIATIONS = new Set([
  'dr', 'mr', 'mrs', 'ms', 'inc', 'ltd', 'jr', 'sr', 'st',
  'vs', 'etc', 'e.g', 'i.e', 'no', 'fig',
  // Common clinical contractions
  'mg', 'ml', 'u.s', 'u.k', 'b.i.d', 't.i.d', 'q.d', 'p.o',
]);

/** Count sentences. Splits on .?! then forward-coalesces fragments
 *  whose final token is a known abbreviation. Forward (into the NEXT
 *  part) rather than backward so "Dr. Smith saw…" is recognised even
 *  when the abbreviation is the FIRST token of the input. */
export function countSentences(text: string): number {
  const trimmed = text.trim();
  if (!trimmed) return 0;
  const rawParts = trimmed.split(/(?<=[.?!])\s+/);
  const parts: string[] = [];
  let carry = '';
  for (const raw of rawParts) {
    const merged = carry ? `${carry} ${raw}` : raw;
    const last = merged.trim().split(/\s+/).pop() ?? '';
    const stripped = last.toLowerCase().replace(/[.?!]+$/, '');
    if (/[.]$/.test(merged.trim()) && ABBREVIATIONS.has(stripped)) {
      carry = merged;
    } else {
      parts.push(merged);
      carry = '';
    }
  }
  if (carry) parts.push(carry);
  const nonEmpty = parts.filter((p) => p.trim().length > 0);
  return Math.max(1, nonEmpty.length);
}

/** Count words. Whitespace-split; strip leading/trailing punctuation. */
export function countWords(text: string): number {
  return text
    .trim()
    .split(/\s+/)
    .filter((w) => /\w/.test(w))
    .length;
}

/** Very simple syllable counter. Counts vowel groups per word, subtracts
 *  silent trailing "e", minimum 1 syllable for any non-empty word. Gets
 *  ~85% accurate on English — more than good enough for a grade-level
 *  check where we only care if the result is above/below a threshold. */
export function countSyllables(word: string): number {
  const w = word.toLowerCase().replace(/[^a-z]/g, '');
  if (!w) return 0;
  // "-le" at end counts as its own syllable ("simple" = 2, not 1).
  const leSuffix = /[^aeiouy]le$/.test(w) ? 1 : 0;
  // Silent trailing "e" after a consonant — always strip, even in the
  // leSuffix case ("simple" → "simpl" then add leSuffix=1 for the
  // /-pl/ syllable → 2 total).
  let base = w;
  if (/[^aeiouy]e$/.test(base)) base = base.slice(0, -1);
  const groups = base.match(/[aeiouy]+/g);
  const count = (groups?.length ?? 0) + leSuffix;
  return Math.max(1, count);
}

/** Total syllables across all words in the text. */
export function totalSyllables(text: string): number {
  let total = 0;
  for (const raw of text.trim().split(/\s+/)) {
    const word = raw.replace(/^[^a-zA-Z]+|[^a-zA-Z]+$/g, '');
    if (word) total += countSyllables(word);
  }
  return total;
}

/**
 * Flesch-Kincaid grade level of `text`. Returns 0 for empty input. A
 * perfectly-readable kid's book hits ~1-3; high-school-level prose is
 * ~8-10; dense medical/legal writing tends to be 14+.
 */
export function fleschKincaidGrade(text: string): number {
  const words = countWords(text);
  const sentences = countSentences(text);
  const syllables = totalSyllables(text);
  if (words === 0 || sentences === 0) return 0;
  return (
    0.39 * (words / sentences) +
    11.8 * (syllables / words) -
    15.59
  );
}
