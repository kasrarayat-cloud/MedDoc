import { describe, expect, it } from "vitest";

import { hasCompleteMfaEnrollment } from "../mfa-enrollment-state";

const NOW = new Date("2026-07-20T09:00:00.000Z");

describe("canonical complete MFA enrollment", () => {
  it("accepts only enabled, nonblank, verified current enrollment", () => {
    expect(
      hasCompleteMfaEnrollment(
        {
          mfaEnabled: true,
          mfaSecret: "SYNTHETIC-SECRET",
          mfaVerifiedAt: new Date("2026-07-20T08:00:00.000Z"),
        },
        NOW,
      ),
    ).toBe(true);
  });

  it("preserves arbitrary nonblank enrolled secrets with Unicode whitespace padding", () => {
    expect(
      hasCompleteMfaEnrollment(
        {
          mfaEnabled: true,
          mfaSecret: "\u00a0synthetic:not-base32\ufeff",
          mfaVerifiedAt: new Date("2026-07-20T08:00:00.000Z"),
        },
        NOW,
      ),
    ).toBe(true);
  });

  it.each([
    ["disabled", false, "SYNTHETIC-SECRET", new Date("2026-07-20T08:00:00Z")],
    ["missing secret", true, null, new Date("2026-07-20T08:00:00Z")],
    ["blank secret", true, "   ", new Date("2026-07-20T08:00:00Z")],
    [
      "tab/newline-only secret",
      true,
      "\t\r\n",
      new Date("2026-07-20T08:00:00Z"),
    ],
    [
      "non-breaking-space-only secret",
      true,
      "\u00a0",
      new Date("2026-07-20T08:00:00Z"),
    ],
    [
      "figure-space-only secret",
      true,
      "\u2007",
      new Date("2026-07-20T08:00:00Z"),
    ],
    [
      "narrow-non-breaking-space-only secret",
      true,
      "\u202f",
      new Date("2026-07-20T08:00:00Z"),
    ],
    [
      "byte-order-mark-only secret",
      true,
      "\ufeff",
      new Date("2026-07-20T08:00:00Z"),
    ],
    ["missing verification", true, "SYNTHETIC-SECRET", null],
    ["invalid verification", true, "SYNTHETIC-SECRET", new Date(Number.NaN)],
    [
      "future verification",
      true,
      "SYNTHETIC-SECRET",
      new Date("2026-07-20T10:00:00Z"),
    ],
    [
      "serialized verification",
      true,
      "SYNTHETIC-SECRET",
      "2026-07-20T08:00:00Z",
    ],
  ])("rejects %s state", (_label, mfaEnabled, mfaSecret, mfaVerifiedAt) => {
    expect(
      hasCompleteMfaEnrollment({ mfaEnabled, mfaSecret, mfaVerifiedAt }, NOW),
    ).toBe(false);
  });
});
