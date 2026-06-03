// ============================================================================
// SOAP structure validator — FIND-P1-015 + FIND-P1-016 closure.
// ----------------------------------------------------------------------------
// Layers 4 (SOAP generation) and 6 (polish) emit markdown — not structured
// JSON — so the Zod / useToolUse pattern from L7a / L2 doesn't apply.
// This module is the markdown counterpart: a lenient structural sanity
// check on the model output before persistence.
//
// Policy (Kasra, 2026-05-14):
//   - Validator is LENIENT by design. Catches obvious failures; does NOT
//     pin exact header formatting beyond "is `## Subjective` (or
//     equivalent) somewhere in the output".
//   - On fail: do NOT crash. The caller writes the raw output to the
//     column anyway (doctor sees what the model produced and can fix
//     it), sets `needsReview = true`, emits a
//     `MODEL_OUTPUT_VALIDATION_FAIL` audit row with NO PHI.
//
// Failure classes detected:
//   1. Empty or near-empty output (< 50 chars after trim) — model
//      returned an effective no-op.
//   2. JSON-shaped output — `{...}` or `[...]` shape. Prompt explicitly
//      says "Output ONLY the SOAP note markdown" (L4) and "the complete
//      revised SOAP note in the same markdown structure" (L6); a JSON
//      envelope means the model ignored the contract.
//   3. Missing SOAP section markers — at least one of Subjective /
//      Objective / Assessment / Plan absent. L4's prompt: "Structure
//      the note with these markdown headings exactly: ## Subjective /
//      ## Objective / ## Assessment / ## Plan". L6's prompt: same
//      markdown structure as the draft.
//
// The header regex is case-insensitive and accepts any whitespace
// between `##` and the section name. This matches the prompt's
// stated structure without locking in exact spacing — a future
// prompt tweak that switches to `**Subjective**` instead of
// `## Subjective` would fail this validator AND should fail (the
// downstream UI parses `## ` headers). When that day comes, the
// validator gets updated.
// ============================================================================

export interface SoapStructureValidation {
  ok: boolean;
  /** Populated when `ok === false`. Short, structured reason string —
   *  safe to log (no PHI from the output). */
  reason: string | null;
  /** Length of the trimmed input. Useful for audit metadata so
   *  operators can see "model returned 12 chars" without surfacing
   *  the content. */
  outputLength: number;
  /** Which sections, if any, were absent. Empty when ok=true OR when
   *  the fail-class is empty/JSON-shape rather than missing-sections. */
  missingSections: readonly string[];
}

/** Minimum length below which the output is treated as effectively
 *  empty. A 50-char SOAP note can't carry the 4 sections + content. */
const MIN_OUTPUT_LENGTH = 50;

/** The 4 SOAP sections, in the order L4's prompt declares them. The
 *  validator does NOT enforce order — order issues are L5's domain.
 *  This list is for presence-only checks. */
const REQUIRED_SECTIONS = [
  'Subjective',
  'Objective',
  'Assessment',
  'Plan',
] as const;

/** Validate the markdown-shape output emitted by L4 (SOAP draft) or L6
 *  (polished SOAP). NEVER throws. Returns a structured result the
 *  caller maps to {persist + audit + needsReview} or {persist only}.
 *
 *  Lenient by design — only checks the contract the prompt actually
 *  asks the model to follow.
 *
 *  Phase 1: `requiredSections` generalizes the check from the fixed 4 SOAP
 *  headers to ANY template's required section labels. It defaults to the
 *  4 SOAP headers, so callers that pass nothing (and the system-default
 *  template, whose labels ARE those 4) get exactly today's behavior. */
export function validateSoapStructure(
  rawText: string | null | undefined,
  requiredSections: readonly string[] = REQUIRED_SECTIONS
): SoapStructureValidation {
  const text = (rawText ?? '').trim();

  if (text.length === 0) {
    return {
      ok: false,
      reason: 'empty output',
      outputLength: 0,
      missingSections: requiredSections,
    };
  }

  if (text.length < MIN_OUTPUT_LENGTH) {
    return {
      ok: false,
      reason: `output too short (${text.length} chars, threshold ${MIN_OUTPUT_LENGTH})`,
      outputLength: text.length,
      missingSections: requiredSections,
    };
  }

  // JSON-shape rejection: the prompt explicitly says "Output ONLY the
  // SOAP note markdown" — a JSON envelope means the model ignored the
  // contract entirely. We don't try to JSON.parse the body (that's
  // expensive on a 5kb SOAP); the bracket-bookends check is enough
  // signal for the obvious-fail class.
  if (
    (text.startsWith('{') && text.endsWith('}')) ||
    (text.startsWith('[') && text.endsWith(']'))
  ) {
    return {
      ok: false,
      reason: 'output is JSON-shaped, expected markdown',
      outputLength: text.length,
      missingSections: requiredSections,
    };
  }

  // Section-presence check: case-insensitive, allows any whitespace
  // between `##` and the section name. The `\\b` (word boundary) on
  // the section name prevents partial matches like
  // `## Subjective findings present in HPI`.
  const missing = requiredSections.filter((section) => {
    const re = new RegExp(`##\\s*${section}\\b`, 'i');
    return !re.test(text);
  });

  if (missing.length > 0) {
    return {
      ok: false,
      reason: `missing SOAP sections: ${missing.join(', ')}`,
      outputLength: text.length,
      missingSections: missing,
    };
  }

  return {
    ok: true,
    reason: null,
    outputLength: text.length,
    missingSections: [],
  };
}
