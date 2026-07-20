import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const repositoryRoot = resolve(process.cwd(), "../..");

function script(name: string): string {
  return readFileSync(
    resolve(repositoryRoot, "packages/db/scripts", name),
    "utf8",
  );
}

const releaseControl = script("template-twin-release-control-pg-test.ts");
const completeMfa = script(
  "template-twin-release-control-mfa-hardening-pg-test.ts",
);
const providerOwnership = script("template-twin-provider-ownership-pg-test.ts");
const staticAsset = script("template-twin-static-asset-revocation-pg-test.ts");
const currentAuthority = script(
  "template-twin-current-authority-concurrency-pg-test.ts",
);
const userSession = script("user-session-concurrency-pg-test.ts");

const CONTROL_DATABASE_ENVIRONMENT = [
  "DATABASE_URL",
  "TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL",
  "TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL",
] as const;

function expectExactControlTargetBinding(source: string): void {
  for (const name of CONTROL_DATABASE_ENVIRONMENT) {
    expect(source).toContain(`"${name}"`);
  }
  expect(source).toContain("value && value !==");
  expect(source).toContain("process.env[name] =");
  expect(source.indexOf("process.env[name] =")).toBeLessThan(
    source.indexOf("async function loadDatabaseBearingModules"),
  );
  expect(source).not.toMatch(
    /^import\s+(?!type\b)[^;]*from\s+["'][^"']*\/release-control["'];/mu,
  );
}

describe("Template Twin PostgreSQL harness database target binding", () => {
  it("binds release-control modules only after all database URLs agree", () => {
    expectExactControlTargetBinding(releaseControl);
    expect(releaseControl).not.toMatch(
      /^import\s+(?!type\b)[^;]*from\s+["'][^"']*\/rollout["'];/mu,
    );
    expect(releaseControl).toContain(
      'import("../../../apps/transcribe-md/src/lib/template-twin/release-control")',
    );
    expect(releaseControl).toContain(
      'import("../../../apps/transcribe-md/src/lib/template-twin/rollout")',
    );
  });

  it("binds and drops the complete-MFA database by the same guarded URL", () => {
    expectExactControlTargetBinding(completeMfa);
    expect(completeMfa).not.toMatch(/import\s+releaseControlDatabase\s+from/u);
    expect(completeMfa).toContain(
      "const adminUrl = new URL(verifiedDatabaseUrl);",
    );
    expect(completeMfa).toContain('cleanup: "exact-test-database-dropped"');
  });

  it("aligns the provider target before any release-control or rollout load", () => {
    for (const name of [
      "TEMPLATE_TWIN_PROVIDER_OWNERSHIP_TEST_DATABASE_URL",
      ...CONTROL_DATABASE_ENVIRONMENT,
    ]) {
      expect(providerOwnership).toContain(`"${name}"`);
    }
    expect(providerOwnership).toContain(
      "value && value !== verifiedDatabaseUrl",
    );
    const alignment = providerOwnership.indexOf(
      "process.env.TEMPLATE_TWIN_PROVIDER_OWNERSHIP_TEST_DATABASE_URL =",
    );
    const releaseControlLoad = providerOwnership.indexOf(
      'await import("../../../apps/transcribe-md/src/lib/template-twin/release-control")',
    );
    const rolloutLoad = providerOwnership.indexOf(
      'await import("../../../apps/transcribe-md/src/lib/template-twin/rollout")',
    );
    expect(alignment).toBeGreaterThanOrEqual(0);
    expect(releaseControlLoad).toBeGreaterThan(alignment);
    expect(rolloutLoad).toBeGreaterThan(alignment);
  });

  it("reports only divergent environment variable names", () => {
    for (const source of [releaseControl, completeMfa, providerOwnership]) {
      expect(source).toContain(
        "`${divergentDatabaseTarget} must exactly match",
      );
      expect(source).not.toMatch(
        /\$\{(?:databaseUrl|verifiedDatabaseUrl|disposableDatabaseUrl)\}.*must exactly match/u,
      );
    }
  });

  it("loads static-asset and current-authority singletons only after binding", () => {
    expect(staticAsset).not.toMatch(
      /^import\s+(?!type\b)[^;]*from\s+["'][^"']*\/static-assets["'];/mu,
    );
    expect(staticAsset).toContain(
      '"TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL"',
    );
    expect(staticAsset).toContain(
      '"TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL"',
    );
    expect(staticAsset.indexOf("process.env.DATABASE_URL =")).toBeLessThan(
      staticAsset.indexOf("const staticAssetsModulePromise"),
    );
    expect(staticAsset).toContain(
      'import("../../../apps/transcribe-md/src/lib/template-twin/static-assets")',
    );

    expect(currentAuthority).not.toContain('import prisma from "../src"');
    expect(currentAuthority.indexOf("process.env.DATABASE_URL =")).toBeLessThan(
      currentAuthority.indexOf('const prismaPromise = import("../src")'),
    );
  });

  it("makes the guarded user-session override authoritative before imports", () => {
    expect(userSession).not.toContain('import prisma from "../src"');
    expect(userSession.indexOf("process.env.DATABASE_URL =")).toBeLessThan(
      userSession.indexOf('import("../src")'),
    );
    expect(userSession.indexOf("process.env.DATABASE_URL =")).toBeLessThan(
      userSession.indexOf('import("../../auth/src/user-session")'),
    );
  });
});
