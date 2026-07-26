// ============================================================================
// One vocabulary, one normaliser — shared by every surface that shows or places
// a verifier-demoted claim.
// ----------------------------------------------------------------------------
// Both of these existed twice: the reason map was copied verbatim into the
// document view, and the section normaliser was reimplemented there with a
// DIFFERENT rule than the adopt action uses. The server strips markdown bold
// and a trailing colon before comparing; the client did not — so a template
// heading like `## **Findings:**` matched server-side and missed client-side,
// and the suggestion fell out of its section into the orphan block. Custom
// templates use colon-suffixed headings routinely.
// ============================================================================

/** DemotionReason → human chip. An unknown reason falls back rather than
 *  printing a raw enum at a clinician. */
const REASON_LABELS: Record<string, string> = {
  model_suggested: 'not stated',
  no_anchor: 'not stated',
  anchor_not_in_transcript: 'quote not in transcript',
  anchor_overlaps_unclear: 'unclear audio',
  digits_unsupported: 'numbers not supported',
  negation_mismatch: 'negation mismatch',
  gloss_unsupported: 'explanation not in transcript',
  process_assertion_unsupported: 'reasoning not stated',
  form_route_unsupported: 'form/route not stated',
  not_entailed: "couldn't verify",
  verifier_failed: "couldn't verify",
};

export function suggestionReasonLabel(reason: string): string {
  return REASON_LABELS[reason] ?? "couldn't verify";
}

/** Normalise a section heading for comparison. MUST match the rule the adopt
 *  action applies when it decides which heading to append under — strip bold
 *  markers, strip a trailing colon, trim, casefold. */
export function normalizeSectionLabel(s: string): string {
  // BYTE-IDENTICAL to normalizeHeading in actions/suggestion-actions.ts. Not
  // "equivalent" — identical. An extra step here (a whitespace collapse, say)
  // would let the client place a claim inline that the server then appends
  // somewhere else, which is worse than either behaviour on its own.
  return s.replace(/\*\*/g, '').replace(/:\s*$/, '').trim().toLowerCase();
}

/** Value equality for a pending E/M change. The RSC payload re-creates the
 *  object on every refresh, so identity comparison reports a change where
 *  there is none. */
export function emChangeEq(
  a: { from: string; to: string } | null | undefined,
  b: { from: string; to: string } | null | undefined,
): boolean {
  if (a == null || b == null) return a == null && b == null;
  return a.from === b.from && a.to === b.to;
}

/**
 * Which top-level section a claim belongs under.
 *
 * The heading SETS diverge, and it bites a template that is live in production.
 * The verifier tags a claim with whatever `#{1,6}` heading it sat under, and the
 * adopt action appends under the same `#{1,6}` match — but the client's
 * parseNoteSections splits on `#{1,2}` only and deliberately folds `###` into
 * its parent's body. The ultrasound report's `### Right` / `### Left` blocks are
 * exactly that shape, so the claim rendered in the "Also suggested" orphan block
 * while the server appended it into the middle of Findings: the doctor reviewed
 * it in one place and signed it in another.
 *
 * So when a claim's section is not a top-level heading, find the section whose
 * BODY carries that sub-heading — which is where the append will actually land.
 */
export function sectionLabelForClaim(
  claimSection: string,
  sections: ReadonlyArray<{ label: string; body: string }>,
): string | null {
  const want = normalizeSectionLabel(claimSection);
  const top = sections.find((s) => normalizeSectionLabel(s.label) === want);
  if (top) return normalizeSectionLabel(top.label);
  const owner = sections.find((s) =>
    s.body
      .split('\n')
      .some((line) => {
        const m = /^#{1,6}\s+(.*)$/.exec(line.trim());
        return m ? normalizeSectionLabel(m[1]) === want : false;
      }),
  );
  return owner ? normalizeSectionLabel(owner.label) : null;
}
