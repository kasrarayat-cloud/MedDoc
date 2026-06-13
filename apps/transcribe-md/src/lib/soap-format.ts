// ============================================================================
// SOAP note formatting helpers — pure string functions, ZERO dependencies.
// ----------------------------------------------------------------------------
// Shared by the worker (anchored-verification body composition) AND the
// server actions (suggestion adopt/dismiss). Kept dependency-free so the
// 'use server' action bundle can import it WITHOUT pulling worker/model-client
// code (the boundary the suggestion-actions module guards).
//
// Both fixes here come from the 2026-06-13 live-voice prod smoke:
//   • EMPTY_SECTION_PLACEHOLDER — a section whose entire drafted content
//     demoted to the suggestions lane must never render as a bare header in a
//     signed note (the empty-Assessment blocker);
//   • renumberOrderedLists — when Plan items demote/adopt, the surviving lines
//     kept their ORIGINAL ordinals (the note rendered 4,5,6,8,9). The Plan the
//     doctor signs must be contiguously numbered over whatever lines actually
//     compose it.
// ============================================================================

/** Back-fill text for a section that lost all its drafted content to the
 *  lane. Visible, clearly a system note, NEVER clinical content; stripped the
 *  moment real content is adopted into the section (stripEmptySectionPlaceholder). */
export const EMPTY_SECTION_PLACEHOLDER =
  '_[All AI-drafted content for this section was set aside for your review — see the suggestions below and adopt before signing.]_';

const SECTION_HEADER_RE = /^#{1,6}\s/;
// TOP-LEVEL ordered-list item only (no leading whitespace) — never touches
// nested/indented lists, and never matches doses ("3.5 mg": no space after the
// dot) or dates ("12/05": slash, not . or )).
const TOP_LEVEL_ORDERED_ITEM_RE = /^(\d+)([.)])(\s+)(.*)$/;

/** Renumber every top-level ordered-list item contiguously (1..n), resetting
 *  at each markdown header. Demotions/adoptions that leave ordinal holes
 *  (1,2,3 then 7) are normalized to 1,2,3,4. Non-list lines, prose, doses,
 *  dates, and nested items are untouched. */
export function renumberOrderedLists(soap: string): string {
  let counter = 0;
  return soap
    .split('\n')
    .map((line) => {
      if (SECTION_HEADER_RE.test(line)) {
        counter = 0;
        return line;
      }
      const m = line.match(TOP_LEVEL_ORDERED_ITEM_RE);
      if (m) {
        counter += 1;
        return `${counter}${m[2]}${m[3]}${m[4]}`;
      }
      return line;
    })
    .join('\n');
}

/** Remove the empty-section placeholder from the section block beginning at
 *  `headingIdx` (the line index of the section header) within `lines`. Returns
 *  a new array. No-op when the placeholder is absent. Used when adopting real
 *  content into a section so the stale placeholder doesn't linger. */
export function stripEmptySectionPlaceholder(
  lines: string[],
  headingIdx: number
): string[] {
  const out = [...lines];
  for (let i = headingIdx + 1; i < out.length; i++) {
    if (SECTION_HEADER_RE.test(out[i])) break;
    if (out[i].trim() === EMPTY_SECTION_PLACEHOLDER) {
      out.splice(i, 1);
      return out;
    }
  }
  return out;
}
