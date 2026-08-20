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
// The third producer, resolver/index.ts's convertValue, is a SEPARATE
// implementation of the same rule and is deliberately NOT folded in here
// today: it converts from a raw fact value under resolver-specific failure
// CODES that its own callers switch on. It already derives FROM THE FACT, so
// it does not carry this defect. Named here so the next reader knows the
// duplication is seen rather than missed.
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
