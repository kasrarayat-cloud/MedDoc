import { describe, expect, it } from "vitest";

import {
  generateMaskedSyntheticDatabaseSecrets,
  registerGithubSecretMasks,
} from "../scripts/synthetic-ci-database-release";

const maskPrefix = "::add-mask::";

describe("synthetic CI database secret masking", () => {
  it("masks all seven raw credentials before returning them to callers", () => {
    const commands: string[] = [];
    const secrets = generateMaskedSyntheticDatabaseSecrets((command) => {
      commands.push(command);
    });
    const values = Object.values(secrets);
    const registered = new Set(
      commands.map((command) => command.slice(maskPrefix.length, -1)),
    );

    expect(Object.keys(secrets).sort()).toEqual([
      "auditDispatcher",
      "authEmailDispatcher",
      "backup",
      "owner",
      "releaseControl",
      "releaseSecurity",
      "runtime",
    ]);
    expect(values.length).toBe(7);
    expect(Object.isFrozen(secrets)).toBe(true);
    expect(new Set(values).size).toBe(7);
    expect(values.every((value) => /^[A-Za-z0-9_-]{43}$/u.test(value))).toBe(
      true,
    );
    expect(commands.length).toBe(7);
    expect(
      commands.every(
        (command) => command.startsWith(maskPrefix) && command.endsWith("\n"),
      ),
    ).toBe(true);
    // Raw components, rather than only composed database URLs, are registered
    // so the runner can redact the same credentials wherever they are embedded.
    expect(values.every((value) => registered.has(value))).toBe(true);
  });

  it("deduplicates exact values without changing first-registration order", () => {
    const commands: string[] = [];

    registerGithubSecretMasks(
      ["first-synthetic", "second-synthetic", "first-synthetic"],
      (command) => commands.push(command),
    );

    expect(commands).toEqual([
      "::add-mask::first-synthetic\n",
      "::add-mask::second-synthetic\n",
    ]);
  });

  it("escapes percent characters as GitHub workflow command data", () => {
    const commands: string[] = [];

    registerGithubSecretMasks(["synthetic%value"], (command) =>
      commands.push(command),
    );

    expect(commands).toEqual(["::add-mask::synthetic%25value\n"]);
  });

  it("rejects the complete batch before output when any value is unsafe", () => {
    for (const invalid of ["", "line\nbreak", "line\rbreak", null]) {
      const commands: string[] = [];

      expect(() =>
        registerGithubSecretMasks(["valid-synthetic", invalid], (command) =>
          commands.push(command),
        ),
      ).toThrow("SYNTHETIC_CI_DATABASE_RELEASE_SECRET_MASK_INVALID");
      expect(commands).toHaveLength(0);
    }
  });

  it("replaces writer failures with a value-free error code", () => {
    expect(() =>
      registerGithubSecretMasks(["synthetic-sensitive-value"], () => {
        throw new Error("writer failure detail");
      }),
    ).toThrow("SYNTHETIC_CI_DATABASE_RELEASE_SECRET_MASK_WRITE_FAILED");
  });
});
