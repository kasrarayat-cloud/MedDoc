import { describe, expect, it } from "vitest";

import {
  hasConfiguredQuillmdRuntimeIdentity,
  isUnconfiguredNextProductionBuild,
  requiresExactQuillmdRuntimeIdentity,
} from "./runtime-identity";

describe("QuillMD runtime identity decision", () => {
  it("preserves an ordinary unconfigured local development process", () => {
    const environment = {
      NODE_ENV: "development",
      NEXT_PHASE: "phase-development-server",
    };

    expect(hasConfiguredQuillmdRuntimeIdentity(environment)).toBe(false);
    expect(requiresExactQuillmdRuntimeIdentity(environment)).toBe(false);
    expect(isUnconfiguredNextProductionBuild(environment)).toBe(false);
  });

  it("identifies an identity-free Next production build", () => {
    const environment = {
      NODE_ENV: "production",
      NEXT_PHASE: "phase-production-build",
    };

    expect(isUnconfiguredNextProductionBuild(environment)).toBe(true);
    expect(requiresExactQuillmdRuntimeIdentity(environment)).toBe(true);
  });

  it.each([
    ["service role", { QUILLMD_SERVICE_ROLE: "" }],
    ["principal profile", { QUILLMD_DATABASE_PRINCIPAL_PROFILE: "" }],
    ["session verifier", { QUILLMD_AUTH_SESSION_VERIFIER_PROFILE: "" }],
  ] as const)(
    "treats an explicitly configured %s as runtime identity",
    (_label, configured) => {
      const environment = {
        NODE_ENV: "development",
        NEXT_PHASE: "phase-production-build",
        ...configured,
      };

      expect(hasConfiguredQuillmdRuntimeIdentity(environment)).toBe(true);
      expect(requiresExactQuillmdRuntimeIdentity(environment)).toBe(true);
      expect(isUnconfiguredNextProductionBuild(environment)).toBe(false);
    },
  );

  it("requires identity proof for a real production server", () => {
    expect(
      requiresExactQuillmdRuntimeIdentity({
        NODE_ENV: "production",
        NEXT_PHASE: "phase-production-server",
      }),
    ).toBe(true);
  });
});
