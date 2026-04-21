// ============================================================================
// SOAP template token dictionary (T-M24)
// ----------------------------------------------------------------------------
// Shared between the upload-time parser, the L7f worker layer, and the
// on-demand filled-docx endpoint so everyone agrees on which tokens the
// AI knows how to fill.
//
// POC scope: 9 tokens covering the major SOAP + chart sections. Extra
// tokens the doctor adds in their template are extracted + surfaced to
// the upload UI as a warning ("unsupported token"), but the template
// still uploads successfully — those slots just fill with empty string
// at generation time.
// ============================================================================

/** Canonical token list. Order matters for consistent UI display. */
export const SUPPORTED_TOKENS = [
  'chief_complaint',
  'hpi',
  'pmh',
  'medications',
  'allergies',
  'ros',
  'exam',
  'assessment',
  'plan',
] as const;

export type SupportedToken = (typeof SUPPORTED_TOKENS)[number];

/** docxtemplater-style mustache pattern, case-sensitive snake_case
 *  only — avoids matching accidental `{{foo bar}}` prose or `{{TODO}}`
 *  user notes. Capture group is the bare token name (no braces). */
const TOKEN_RE = /\{\{([a-z_]+)\}\}/g;

/** Extract every `{{token_name}}` from the template's plain-text body
 *  (post-mammoth) and return a deduplicated, order-preserved array.
 *  Order = first-occurrence so the upload-preview chip row reads
 *  naturally ("Tokens found: hpi, exam, …"). */
export function extractTokens(text: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const match of text.matchAll(TOKEN_RE)) {
    const name = match[1];
    if (!seen.has(name)) {
      seen.add(name);
      out.push(name);
    }
  }
  return out;
}

/** Split extracted tokens into (supported, unsupported) buckets.
 *  The upload UI surfaces the unsupported list as a warning; the
 *  L7f layer only attempts to fill tokens in the supported set.
 *  Unsupported tokens land as empty-string at generation time so
 *  docxtemplater doesn't leave literal `{{custom_field}}` text in
 *  the filled output. */
export function partitionTokens(tokens: string[]): {
  supported: SupportedToken[];
  unsupported: string[];
} {
  const supportedSet = new Set<string>(SUPPORTED_TOKENS);
  const supported: SupportedToken[] = [];
  const unsupported: string[] = [];
  for (const token of tokens) {
    if (supportedSet.has(token)) {
      supported.push(token as SupportedToken);
    } else {
      unsupported.push(token);
    }
  }
  return { supported, unsupported };
}
