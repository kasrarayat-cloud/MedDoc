// ============================================================================
// Character-level Levenshtein edit distance (T-M14.1)
// ----------------------------------------------------------------------------
// Used by the sign-time capture hook to score "how much did the doctor
// change". Output is stored in doctor_edit_patterns.editDistance and
// indexed so future "find the visits this doctor rewrote most" queries
// are a cheap ORDER BY DESC.
//
// Implementation notes
//   - Two-row dynamic programming → O(n) memory for O(nm) time.
//   - Inputs capped at MAX_CHARS_PER_SIDE to keep worst-case runtime
//     well under a second. Real-world SOAP notes land in the 1-3K char
//     range; the cap only trips on extreme outliers (copy-paste of a
//     chapter). For those, the returned number is a lower-bound of the
//     true distance — still sortable, still a useful signal.
// ============================================================================

const MAX_CHARS_PER_SIDE = 8000;

export function charLevenshtein(a: string, b: string): number {
  const s1 = a.length > MAX_CHARS_PER_SIDE ? a.slice(0, MAX_CHARS_PER_SIDE) : a;
  const s2 = b.length > MAX_CHARS_PER_SIDE ? b.slice(0, MAX_CHARS_PER_SIDE) : b;

  const m = s1.length;
  const n = s2.length;
  if (m === 0) return n;
  if (n === 0) return m;

  let prev = new Array<number>(n + 1);
  let curr = new Array<number>(n + 1);
  for (let j = 0; j <= n; j++) prev[j] = j;

  for (let i = 1; i <= m; i++) {
    curr[0] = i;
    const c1 = s1.charCodeAt(i - 1);
    for (let j = 1; j <= n; j++) {
      const cost = c1 === s2.charCodeAt(j - 1) ? 0 : 1;
      const del = prev[j] + 1;
      const ins = curr[j - 1] + 1;
      const sub = prev[j - 1] + cost;
      curr[j] = del < ins ? (del < sub ? del : sub) : ins < sub ? ins : sub;
    }
    const tmp = prev;
    prev = curr;
    curr = tmp;
  }
  return prev[n];
}
