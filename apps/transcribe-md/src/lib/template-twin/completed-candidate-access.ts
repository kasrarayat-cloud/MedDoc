export const COMPLETED_CANDIDATE_SYNTHETIC_MODE =
  "synthetic-review-v1" as const;

/**
 * The first completed-document slice is deliberately unavailable unless an
 * operator selects the exact synthetic-only mode. This is not a production
 * PHI authorization switch and cannot be widened with a truthy value.
 */
export function completedCandidateSyntheticModeEnabled(
  env: Readonly<Record<string, string | undefined>> = process.env,
): boolean {
  return (
    env.TEMPLATE_TWIN_COMPLETED_CANDIDATE_MODE?.trim() ===
    COMPLETED_CANDIDATE_SYNTHETIC_MODE
  );
}
