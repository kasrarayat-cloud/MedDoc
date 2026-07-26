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
 *  markers, strip a trailing colon, collapse whitespace, casefold. */
export function normalizeSectionLabel(s: string): string {
  return s
    .replace(/\*\*/g, '')
    .replace(/:\s*$/, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}
