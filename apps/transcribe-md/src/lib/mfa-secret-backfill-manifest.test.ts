import { describe, expect, it } from "vitest";

import {
  buildMfaSecretBackfillCandidateManifest,
  type MfaSecretBackfillManifestEntry,
} from "./mfa-secret-backfill-manifest";

function entry(
  overrides: Partial<MfaSecretBackfillManifestEntry> = {},
): MfaSecretBackfillManifestEntry {
  return {
    id: "synthetic-user-a",
    practiceId: "synthetic-practice-a",
    mfaEnabled: true,
    verifiedTimestamp: "2026-07-20T12:00:00.000000Z",
    secretState: "legacy",
    totalRecoveryVerifierCount: 2,
    currentRecoveryVerifierCount: 1,
    legacyRecoveryVerifierCount: 1,
    ...overrides,
  };
}

describe("MFA backfill candidate manifest", () => {
  it("is deterministic, order-independent, and non-identifying on output", () => {
    const first = entry();
    const second = entry({
      id: "synthetic-user-b",
      practiceId: "synthetic-practice-b",
    });
    const forward = buildMfaSecretBackfillCandidateManifest([first, second]);
    const reverse = buildMfaSecretBackfillCandidateManifest([second, first]);

    expect(forward).toBe(reverse);
    expect(forward).toMatch(/^[0-9a-f]{64}$/u);
    expect(forward).not.toContain(first.id);
    expect(forward).not.toContain(first.practiceId);
  });

  it.each([
    ["identity", { id: "synthetic-user-replacement" }],
    ["practice", { practiceId: "synthetic-practice-replacement" }],
    ["enabled state", { mfaEnabled: false }],
    ["verification time", { verifiedTimestamp: "null" }],
    [
      "verification microsecond",
      { verifiedTimestamp: "2026-07-20T12:00:00.000001Z" },
    ],
    ["secret category", { secretState: "encrypted" as const }],
    ["total count", { totalRecoveryVerifierCount: 3 }],
    ["current count", { currentRecoveryVerifierCount: 0 }],
    ["legacy count", { legacyRecoveryVerifierCount: 2 }],
  ])("changes when reviewed candidate %s changes", (_label, override) => {
    expect(buildMfaSecretBackfillCandidateManifest([entry(override)])).not.toBe(
      buildMfaSecretBackfillCandidateManifest([entry()]),
    );
  });
});
