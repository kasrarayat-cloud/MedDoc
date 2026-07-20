export interface MfaEnrollmentState {
  readonly mfaEnabled?: unknown;
  readonly mfaSecret?: unknown;
  readonly mfaVerifiedAt?: unknown;
}

/**
 * Canonical fail-closed definition shared by every in-process admin gate.
 * String.trim() deliberately defines the accepted nonblank boundary; database
 * predicates must remove the same ECMAScript whitespace code points.
 */
export function hasCompleteMfaEnrollment(
  state: MfaEnrollmentState,
  now: Date = new Date(),
): boolean {
  return (
    state.mfaEnabled === true &&
    typeof state.mfaSecret === "string" &&
    state.mfaSecret.trim().length > 0 &&
    state.mfaVerifiedAt instanceof Date &&
    !Number.isNaN(state.mfaVerifiedAt.getTime()) &&
    state.mfaVerifiedAt.getTime() <= now.getTime()
  );
}
