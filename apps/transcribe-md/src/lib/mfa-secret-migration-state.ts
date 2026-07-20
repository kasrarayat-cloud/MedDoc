import { hasCompleteMfaEnrollment } from "@/lib/mfa-enrollment-state";

export interface MfaMigrationEnrollmentState {
  mfaEnabled: boolean;
  mfaVerifiedAt: Date | null;
  hasAuthenticStoredSecret: boolean;
}

/**
 * Migration-specific use of the canonical enrollment definition. A legacy
 * Base32 secret or authenticated envelope can supply the stored-secret leg;
 * missing, malformed, unknown-key, wrong-user, or tampered values cannot.
 * Disabled accounts are not incomplete enrollments.
 */
export function isIncompleteEnabledMfaEnrollment(
  state: MfaMigrationEnrollmentState,
  censusAt: Date,
): boolean {
  if (!state.mfaEnabled) return false;
  return !hasCompleteMfaEnrollment(
    {
      mfaEnabled: true,
      mfaSecret: state.hasAuthenticStoredSecret
        ? "authenticated-migration-secret"
        : null,
      mfaVerifiedAt: state.mfaVerifiedAt,
    },
    censusAt,
  );
}
