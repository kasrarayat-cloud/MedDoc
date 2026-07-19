const ALLOWED_CORRECTION_STRINGS = new Set([
  "synthetic wrist discomfort",
  "Current",
  "Follow-up",
  "2099-07-16",
  "Syntheticmed",
  "Use synthetic brace",
  "synthetic brace at night",
  "synthetic follow-up tolerated well",
]);

/** Closed synthetic correction vocabulary for the versioned staging fixture. */
export function isTemplateTwinStagingQaCorrectionValueAllowed(
  value:
    | string
    | number
    | boolean
    | string[]
    | Record<string, string | null>[]
    | null,
): boolean {
  if (value === null || typeof value === "boolean") return true;
  return typeof value === "string" && ALLOWED_CORRECTION_STRINGS.has(value);
}
