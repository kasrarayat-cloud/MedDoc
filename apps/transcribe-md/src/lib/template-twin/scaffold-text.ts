// ============================================================================
// SCAFFOLD TEXT — the closed token set, the placeholder scan, and the furniture
// predicate. ONE definition, many readers (TOKEN-1 substitution, PANEL-1 offer,
// the export-bytes gate, the cert self-test).
// ----------------------------------------------------------------------------
// ⚠️ THIS IS A PURE LEAF, BY DESIGN. It imports NOTHING — no zod, no crypto, no
// prisma — exactly like `note-template-docx/placeholder-option.ts`. That is what
// lets the CLIENT panel and the SERVER fill/gate share the SAME predicate
// instead of each carrying a copy that drifts (the one-rule-many-readers trap).
// The age arithmetic that {age} needs is NOT here (it lives in visit-metadata.ts
// and drags zod); the server-only substitution module imports both this leaf and
// that arithmetic. This leaf answers only string-shape questions.
// ============================================================================

/**
 * THE CLOSED, REGISTERED TOKEN SET. A scaffold may contain ONLY these tokens;
 * substitution touches ONLY these; the gate treats any OTHER `{word}` as a
 * defect. Growing this set is a deliberate edit here, and the registry in
 * `token-substitution.ts` must gain a resolver for the new token in the same
 * change — a token with no resolver is a token that prints its braces.
 */
export const SUBSTITUTABLE_TOKENS = ['patient', 'age'] as const;
export type SubstitutableToken = (typeof SUBSTITUTABLE_TOKENS)[number];

/** The recogniser, BUILT FROM THE KEYS — never a generic `\{[^}]+\}`. A generic
 *  brace class would collide with the `{{one of: ...}}` choice marker
 *  (`picks-bridge.ts`) and with literal braces in clinical prose. */
export function substitutableTokenPattern(): RegExp {
  return new RegExp(`\\{(${SUBSTITUTABLE_TOKENS.join('|')})\\}`, 'g');
}

/** True if the text carries at least one REGISTERED token. Used by PANEL-1 to
 *  drop a control TOKEN-1 fills, and by the substitution to decide whether to
 *  act at all. */
export function hasSubstitutableTokens(text: string | null | undefined): boolean {
  if (!text) return false;
  return substitutableTokenPattern().test(text);
}

/** The registered tokens present in the text, de-duplicated, in registry order. */
export function substitutableTokensIn(text: string | null | undefined): SubstitutableToken[] {
  if (!text) return [];
  return SUBSTITUTABLE_TOKENS.filter((t) => text.includes(`{${t}}`));
}

/**
 * THE EXPORT-BYTES GATE PREDICATE. Given already-extracted VISIBLE text (never
 * raw XML — see the extractor), return every brace placeholder that survived.
 *
 * ⚠️ It flags ANY single-brace `{word}` token — a registered one that was not
 * substituted AND an UNREGISTERED `{foo}` that a template should never contain —
 * but NEVER the double-brace `{{one of: ...}}` choice marker (stripped first),
 * so a legitimate marker cannot trip it. A lone `{` or `}` in clinical prose
 * does not match `{word}` and is left alone.
 */
export function residualPlaceholders(text: string | null | undefined): string[] {
  if (!text) return [];
  // ⚠️ A `{word}` placeholder is a SINGLE brace on each side, with no spaces.
  // The `{{one of: …}}` choice marker (picks-bridge.ts) has DOUBLE braces and
  // always contains "one of:" plus spaces/commas, so a single-word `{word}`
  // pattern NEVER matches inside it. We therefore do NOT strip `{{…}}` first —
  // an earlier `.replace(/\{\{[^}]*\}\}/g, ' ')` greedily ATE an embedded
  // `{patient}` (adversarial finding), letting a real residual hide inside a
  // marker. Matching `{word}` directly is both simpler and strictly safer.
  const hits = text.match(/\{[A-Za-z][A-Za-z0-9_]*\}/g);
  return hits ? Array.from(new Set(hits)) : [];
}

/** The subset of {@link residualPlaceholders} that are NOT registered tokens —
 *  i.e. an `{mrn}`/`{provider}` a scaffold should never contain, because nothing
 *  substitutes it and it would print its braces. The certification self-test
 *  scans scaffold TEXTS with this (a registered `{patient}`/`{age}` is fine — it
 *  substitutes on insert; an unregistered one can never be made safe). */
export function unregisteredPlaceholders(text: string | null | undefined): string[] {
  return residualPlaceholders(text).filter(
    (p) => !SUBSTITUTABLE_TOKENS.some((t) => p === `{${t}}`),
  );
}

/**
 * FURNITURE — a scaffold that is decoration, not wording: underscores, dashes,
 * box rules, dots, light separators, whitespace. PANEL-1(a): never offer such a
 * control as an "insert my default", because its "default" is a fill-in line.
 *
 * The test is structural: after trimming, a non-empty string that contains NO
 * letter and NO digit (any script) is furniture. This subsumes the owner's
 * "underscores, dashes, whitespace only" and also catches a rule of dots or
 * separators, while a scaffold with any real word (or a token like `{age}`,
 * which contains letters) is NOT furniture.
 */
export function isFurnitureScaffold(text: string | null | undefined): boolean {
  if (!text) return false;
  const trimmed = text.trim();
  if (trimmed.length === 0) return false;
  return !/[\p{L}\p{N}]/u.test(trimmed);
}

/**
 * TOKEN-ONLY — a scaffold whose entire content is registered tokens (plus, at
 * most, furniture: "{patient}", "{age}", "{patient}, {age}"). PANEL-1(d): TOKEN-1
 * fills such a control ENTIRELY from the visit record, so it is not a wording the
 * doctor chooses — drop it from the "insert my default" offer. A scaffold that
 * MIXES a token with real prose (an HPI intro like "{patient} is a pleasant
 * {age}-year-old presenting for …") is NOT token-only: the prose is the doctor's
 * default and stays offered; TOKEN-1 substitutes the tokens within it at fill.
 */
export function isTokenOnlyScaffold(text: string | null | undefined): boolean {
  if (!text) return false;
  if (!hasSubstitutableTokens(text)) return false;
  const withoutTokens = text.replace(substitutableTokenPattern(), '');
  return withoutTokens.trim().length === 0 || isFurnitureScaffold(withoutTokens);
}
