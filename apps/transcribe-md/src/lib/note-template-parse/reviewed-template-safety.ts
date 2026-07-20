import { detectStructuredPhi } from "./phi-gate";

export const REVIEWED_TEMPLATE_PRIVACY_REJECTION =
  "This format contains populated or patient-like text. Remove patient details and completed-note content before saving or activating it.";

const PATIENT_LIKE_TEXT_RE =
  /\b(?:(?:patient|he|she|they)\s+(?:reports?|denies|has|had|was|is)|(?:reports?|reported|denies|denied|presented|treated|diagnosed)\s+(?:with|for|that))\b/iu;
const PATIENT_NAME_VALUE_RE =
  /\bpatient(?:\s+name)?\s*(?::|=|-|\bis\b)?\s+\p{Lu}[\p{L}\p{M}'-]{1,60}\s+\p{Lu}[\p{L}\p{M}'-]{1,60}\b/iu;
const CLINICAL_VALUE_RE =
  /(?:\b(?:bp|blood\s+pressure)\s*[:=]?\s*\d{2,3}\s*\/\s*\d{2,3}\b|\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|kg|lb|cm|mm|mmhg|bpm)\b|\b\d+(?:\.\d+)?%)/iu;

function allTemplateStrings(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(allTemplateStrings);
  if (!value || typeof value !== "object") return [];
  return Object.values(value).flatMap(allTemplateStrings);
}

function hasPopulatedDefault(value: unknown): boolean {
  if (Array.isArray(value)) return value.some(hasPopulatedDefault);
  if (!value || typeof value !== "object") return false;
  return Object.entries(value).some(
    ([key, child]) =>
      (key === "defaultText" &&
        typeof child === "string" &&
        child.trim().length > 0) ||
      hasPopulatedDefault(child),
  );
}

/**
 * Deterministic fail-closed boundary shared by sample preview, save, and
 * activation. A legacy structured template is allowed to describe blank
 * structure only. Patient-like values, clinical measurements, identifiers,
 * and every populated default require a separately reviewed workflow.
 */
export function hasLocallyUnsafeReviewedTemplateContent(
  value: unknown,
): boolean {
  if (hasPopulatedDefault(value)) return true;
  return allTemplateStrings(value).some(
    (text) =>
      detectStructuredPhi(text).length > 0 ||
      PATIENT_LIKE_TEXT_RE.test(text) ||
      PATIENT_NAME_VALUE_RE.test(text) ||
      CLINICAL_VALUE_RE.test(text),
  );
}
