import { describe, expect, it } from "vitest";

import { isIncompleteEnabledMfaEnrollment } from "./mfa-secret-migration-state";

const CENSUS_AT = new Date("2026-07-20T12:00:00.000Z");

describe("MFA migration enrollment census", () => {
  it.each([
    ["missing secret", false, new Date("2026-07-20T11:00:00.000Z")],
    ["null verification", true, null],
    ["future verification", true, new Date("2026-07-20T12:00:00.001Z")],
    ["invalid verification", true, new Date(Number.NaN)],
  ])(
    "marks an enabled %s state incomplete",
    (_label, authentic, verifiedAt) => {
      expect(
        isIncompleteEnabledMfaEnrollment(
          {
            mfaEnabled: true,
            hasAuthenticStoredSecret: authentic,
            mfaVerifiedAt: verifiedAt,
          },
          CENSUS_AT,
        ),
      ).toBe(true);
    },
  );

  it.each(["legacy", "encrypted"])(
    "accepts a structurally authenticated %s secret with nonfuture verification",
    () => {
      expect(
        isIncompleteEnabledMfaEnrollment(
          {
            mfaEnabled: true,
            hasAuthenticStoredSecret: true,
            mfaVerifiedAt: new Date("2026-07-20T11:59:59.999Z"),
          },
          CENSUS_AT,
        ),
      ).toBe(false);
    },
  );

  it("does not classify a disabled account as an incomplete enrollment", () => {
    expect(
      isIncompleteEnabledMfaEnrollment(
        {
          mfaEnabled: false,
          hasAuthenticStoredSecret: false,
          mfaVerifiedAt: null,
        },
        CENSUS_AT,
      ),
    ).toBe(false);
  });
});
