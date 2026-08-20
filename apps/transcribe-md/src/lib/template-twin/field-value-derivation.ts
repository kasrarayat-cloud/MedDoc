// ============================================================================
// Template Twin — THE derivation of a field's value from its cited fact.
// ----------------------------------------------------------------------------
// ONE RULE, EVERY CALLER. This module exists because the rule had two callers
// and only one of them was using it.
//
// The validator re-derives a supported field's value from the fact the
// resolution cites and compares the two with strict `===`
// (validation/index.ts, assertionSupported). Anything that WRITES a supported
// resolution must therefore write exactly what this function returns for that
// (field, mapping, fact) — otherwise the value is refused as
// ASSERTION_NOT_SUPPORTED, which is a BLOCKING issue and kills the entire
// native fill for the visit, not merely the one cell.
//
// ⚠️ WHAT THIS COST, AND WHY IT IS A MODULE RATHER THAN A COMMENT.
// bridge-fill.ts wrote the MODEL'S markdown cell text — "3.10" — while the
// validator re-derived the FACT'S own value — "3.1". The two agree
// NUMERICALLY (the matcher had already proved identity to 1e-9) and differ
// only in TEXT, so `"3.1" === "3.10"` was false and two cells of the owner's
// real template blocked certification three times running. Reproduced and
// named at FILE:LINE by F5-d(a); fixed here per ruling #135.
//
// The failure needs a trailing zero to appear at all, which is why 18 of 20
// diameters round-tripped fine and nothing surfaced it for weeks. A doctor
// dictating "three point one zero millimetres" reproduces it on a real visit.
//
// ⚠️ THIS IS A TIGHTENING, NOT A LOOSENING. The document now carries the CITED
// FACT'S value instead of model-authored text. Making the validator compare
// numerically instead would have "worked" and would have weakened a shipped
// gate on the clinical path — explicitly ruled out by #135.
//
// ⚠️ PROVENANCE, STATED EXACTLY. `isStrictIsoDate` and `exactOption` came out
// of validation/index.ts byte-identical. `deriveFieldValueFromFact` is its
// `valueFromFact` plus exactly ONE line — `if (!mapping) return null;` — and
// nothing else; measured by comparing normalised function bodies against
// origin/main rather than by eye. The validator cannot reach that line (it
// refuses a mapping-less field with MAPPING_MISSING before assertionSupported
// runs), so its behaviour is unchanged.
//
// The third producer, resolver/index.ts's convertValue, is a SEPARATE
// implementation of the same rule and is deliberately NOT folded in here
// today: it converts from a raw fact value under resolver-specific failure
// CODES that its own callers switch on, and it already derives FROM THE FACT
// rather than from model text — so it does not carry THIS defect (the bridge's
// note-text copy). Named here so the next reader knows the duplication is seen
// rather than missed.
//
// ⚠️ AN EARLIER VERSION OF THAT SENTENCE STOPPED AT "does not carry this
// defect", AND AN ADVERSARIAL PASS CORRECTLY READ IT AS WIDER THAN INTENDED.
// The resolver carries the same FAMILY — a writer and the validator disagreeing
// by one character, costing the whole document — through a different door:
// `resolver/index.ts:107` TRIMS before matching an option and this module does
// not (nor did the validator's private copy it came from, so the extraction
// introduced nothing). A `single_select` fact value of `"Normal "` therefore
// resolves in the resolver and fails to re-derive in the validator →
// ASSERTION_NOT_SUPPORTED → the native document is silently withheld. That is
// live on `main` today, it is OUT OF SCOPE for F5-d, and it is filed in RELAY
// rather than fixed here, because folding it in is a behaviour change to the
// resolver on the clinical path and needs its own proof.
//
// ⚠️ AND THE DUPLICATION LIST IS THREE, NOT TWO — an adversarial pass caught
// this note being short by one. `isStrictIsoDate` also has a THIRD copy at
// note-template-docx/renderer.ts:883, outside this package entirely. None of
// the three is folded in today; enumerating them is the point, because "the
// duplication is seen" is a claim that decays the moment a copy is missed.
// ============================================================================

import type { EncounterFact, SemanticMapping, TemplateField } from './ir';
import { parseExplicitNumberAndUnit } from './encounter-facts';

export function isStrictIsoDate(value: string): boolean {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  return (
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day
  );
}

export function exactOption(
  field: TemplateField,
  value: string,
): { value: string; displayText: string; ordinal: number } | null {
  return (
    field.allowedOptions.find(
      (option) => option.value === value || option.displayText === value,
    ) ?? null
  );
}

/**
 * The value this field must carry if it cites this fact — or `null` when the
 * fact cannot support a renderable value for this field at all.
 *
 * A `null` return is a REFUSAL and must be honoured as one: a writer that sees
 * null leaves the field blank with a named reason. It must never fall back to
 * some other value, because "some other value" is precisely the defect this
 * module was extracted to remove.
 *
 * ⚠️ THE RETURN TYPE IS PART OF THE CONTRACT, NOT AN IMPLEMENTATION DETAIL.
 * A `number` field returns a NUMBER and a `narrative_text` field returns a
 * STRING, and note-template-docx/renderer.ts:778-824 independently refuses the
 * wrong one with FIELD_VALUE_INVALID. So a caller that stringifies this result
 * breaks the renderer even where it satisfies the validator. Write it through
 * unchanged.
 *
 * `mapping` is OPTIONAL because only the `measurement` branch consults it (for
 * unitPolicy); every other kind derives from the fact alone. A `measurement`
 * field with no mapping REFUSES rather than guessing a unit policy — there is
 * no safe default, and the validator, which always has the mapping, would
 * refuse the guess anyway.
 *
 * ⚠️⚠️ **"WRITE IT THROUGH UNCHANGED" IS SOUND FOR FIVE OF THE SEVEN KINDS AND
 * WRONG FOR TWO.** This function was born COMPARE-ONLY inside the validator,
 * where a return value is only ever `===`-tested. Making it public made its
 * return a WRITE-SIDE contract, and for two kinds that contract is incomplete.
 * Both were found by an adversarial pass; both are stated here rather than
 * papered over, because the previous version of this docstring told a caller to
 * do something that produces a blocking issue and a thrown render:
 *
 *  - **`multi_select` returns a bare STRING, and every consumer needs
 *    `string[]`.** Writing it through yields MULTI_SELECT_TYPE_INVALID
 *    (blocking) plus `failTemplateDocxRender('FIELD_VALUE_INVALID')`. Compare
 *    against a `string[]` element; do not write the result.
 *  - **`single_select` returns the option's VALUE and drops its ORDINAL**,
 *    which is the half a writer needs: the validator checks
 *    `selectedOptionOrdinal` against the option (DROPDOWN_ORDINAL_MISMATCH) and
 *    the renderer resolves the option THROUGH the ordinal. Its sibling
 *    implementation, resolver/index.ts's `convertValue`, returns the PAIR for
 *    exactly this reason.
 *
 * So: any future writer beyond the measurement bridge must handle those two
 * kinds explicitly or refuse them, as `supportedNumeric` does. The refusal
 * lives on the CALLER today, which is the weaker place for it — recorded as a
 * known limit rather than claimed as a design.
 */
export function deriveFieldValueFromFact(
  field: TemplateField,
  mapping: SemanticMapping | undefined,
  fact: EncounterFact,
): string | number | boolean | null {
  switch (field.kind) {
    case 'narrative_text':
      return typeof fact.value === 'string' ? fact.value : null;
    case 'single_select': {
      if (typeof fact.value !== 'string') return null;
      return exactOption(field, fact.value)?.value ?? null;
    }
    case 'multi_select':
      return typeof fact.value === 'string'
        ? exactOption(field, fact.value)?.value ?? null
        : null;
    case 'checkbox':
      return fact.polarity === 'affirmed'
        ? true
        : fact.polarity === 'denied'
          ? false
          : null;
    case 'date':
      return typeof fact.value === 'string' && isStrictIsoDate(fact.value.trim())
        ? fact.value.trim()
        : null;
    case 'number': {
      const parsed = parseExplicitNumberAndUnit(fact.value);
      const number = fact.number ?? parsed.number;
      const unit = fact.unit ?? parsed.unit;
      return number !== null && unit === null ? number : null;
    }
    case 'measurement': {
      if (!mapping) return null;
      const parsed = parseExplicitNumberAndUnit(fact.value);
      const number = fact.number ?? parsed.number;
      const unit = fact.unit ?? parsed.unit;
      if (number === null) return null;
      if (mapping.unitPolicy === 'required' && !unit) return null;
      if (mapping.unitPolicy === 'forbidden' && unit) return null;
      return unit ? `${number} ${unit}` : number;
    }
  }
}
