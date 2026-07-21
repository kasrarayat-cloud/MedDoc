import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { QUILLMD_PRODUCTION_RUNTIME_DATABASE_PRINCIPALS } from "@meddoc/db/production-runtime-principal";

const ROOT = path.resolve(__dirname, "../../../..");
const read = (relativePath: string) =>
  readFileSync(path.join(ROOT, relativePath), "utf8");

const transcribeInstrumentation = read(
  "apps/transcribe-md/src/instrumentation.ts",
);
const meddocInstrumentation = read("apps/meddoc-pro/instrumentation.ts");
const worker = read("apps/transcribe-md/src/worker.ts");
const auditDispatcher = read("apps/transcribe-md/src/audit-dispatcher.ts");
const authEmailDispatcher = read(
  "apps/transcribe-md/src/auth-email-dispatcher.ts",
);
const compose = read("docker-compose.yml");
const qaCompose = read("docker-compose.qa.yml");
const runtimeCensus = read("scripts/template-twin-runtime-census.mjs");
const principalCensus = read("scripts/database-principal-runtime-census.mjs");
const runtimeSwap = read("scripts/template-twin-runtime-swap.sh");
const dbPackage = read("packages/db/package.json");
const humanReleaseWorkflow = read(
  ".github/workflows/template-twin-human-release-gate.yml",
);
const nextRuntimeEntrypoint = read(
  "scripts/quillmd-next-runtime-entrypoint.mjs",
);
const transcribeDockerfile = read("apps/transcribe-md/Dockerfile");
const meddocDockerfile = read("apps/meddoc-pro/Dockerfile");
const transcribePackage = read("apps/transcribe-md/package.json");
const meddocPackage = read("apps/meddoc-pro/package.json");
const runtimeIdentity = read("packages/auth/src/runtime-identity.ts");

describe("production runtime principal startup contract", () => {
  it("runs the exact-principal gate from both Next startup hooks", () => {
    const transcribePrincipal = transcribeInstrumentation.indexOf(
      "await assertProductionRuntimeDatabasePrincipal({",
    );
    expect(transcribePrincipal).toBeGreaterThan(-1);
    expect(transcribePrincipal).toBeLessThan(
      transcribeInstrumentation.indexOf(
        "assertAdminSurfaceRuntimeConfiguration(process.env)",
      ),
    );
    expect(transcribeInstrumentation).toContain(
      "evaluateTemplateTwinStagingQaResourceBoundary(process.env).allowed",
    );
    expect(transcribeInstrumentation).toContain(
      "if (isUnconfiguredNextProductionBuild(process.env))",
    );
    expect(transcribeInstrumentation).toContain(
      "if (requiresExactQuillmdRuntimeIdentity(process.env))",
    );
    expect(
      transcribeInstrumentation.indexOf(
        'await import("@meddoc/auth/runtime-identity")',
      ),
    ).toBeGreaterThan(transcribeInstrumentation.indexOf("try {"));
    expect(
      transcribeInstrumentation.indexOf(
        'await import("@meddoc/auth/runtime-identity")',
      ),
    ).toBeLessThan(
      transcribeInstrumentation.indexOf(
        "terminateForFatalStartupConfiguration(error)",
      ),
    );

    const meddocPrincipal = meddocInstrumentation.indexOf(
      "await assertProductionRuntimeDatabasePrincipal({",
    );
    expect(meddocPrincipal).toBeGreaterThan(-1);
    expect(meddocPrincipal).toBeLessThan(
      meddocInstrumentation.indexOf("sentry.server.config"),
    );
    expect(meddocInstrumentation).toContain(
      "syntheticQaResourceBoundaryAllowed: false",
    );
    expect(meddocInstrumentation).toContain(
      "!isUnconfiguredNextProductionBuild(process.env)",
    );
    expect(meddocInstrumentation).toContain(
      "requiresExactQuillmdRuntimeIdentity(process.env)",
    );
    expect(meddocInstrumentation).toContain(
      "terminateForFatalStartupConfiguration(error)",
    );
    expect(meddocInstrumentation).toContain(
      'import("./src/lib/fatal-startup")',
    );
    expect(meddocInstrumentation).toContain(
      'process.env.QUILLMD_SERVICE_ROLE !== "meddoc-pro-app"',
    );
    expect(meddocInstrumentation).toContain('"exact-production-v1"');
    expect(meddocInstrumentation).toContain(
      "Boolean(process.env.QUILLMD_AUTH_SESSION_VERIFIER_PROFILE?.trim())",
    );
    expect(runtimeIdentity).toContain('environment.NODE_ENV === "production"');
    for (const key of [
      "QUILLMD_SERVICE_ROLE",
      "QUILLMD_DATABASE_PRINCIPAL_PROFILE",
      "QUILLMD_AUTH_SESSION_VERIFIER_PROFILE",
    ]) {
      expect(runtimeIdentity).toContain(`"${key}"`);
    }
    expect(runtimeIdentity).toContain("environment[key] !== undefined");
  });

  it("rejects a build-only phase at every immutable Next server entrypoint", () => {
    expect(nextRuntimeEntrypoint).toContain(
      "environment.NEXT_PHASE === BUILD_PHASE",
    );
    expect(nextRuntimeEntrypoint).toContain(
      'code: "QUILLMD_RUNTIME_ENTRYPOINT_REJECTED"',
    );
    for (const source of [
      transcribeDockerfile,
      meddocDockerfile,
      transcribePackage,
      meddocPackage,
    ]) {
      expect(source).toContain("quillmd-next-runtime-entrypoint.mjs");
    }
  });

  it("proves the worker principal before constructing any queue consumer", () => {
    const principalGate = worker.indexOf(
      "await assertProductionRuntimeDatabasePrincipal({",
    );
    expect(principalGate).toBeGreaterThan(-1);
    expect(principalGate).toBeLessThan(
      worker.indexOf("const worker = new Worker<ProcessVisitPayload>"),
    );
    expect(worker).toContain(
      "evaluateTemplateTwinStagingQaResourceBoundary(process.env).allowed",
    );
  });

  it("preserves both dedicated dispatcher exact-principal gates", () => {
    for (const dispatcher of [auditDispatcher, authEmailDispatcher]) {
      expect(dispatcher).toContain(
        'import { assertExactDatabasePrincipal } from "@/lib/exact-database-principal"',
      );
      expect(dispatcher).toContain(
        "QUILLMD_EXACT_PRODUCTION_DATABASE_PRINCIPAL_PROFILE",
      );
      expect(dispatcher).toContain(
        "process.env.QUILLMD_DATABASE_PRINCIPAL_PROFILE !==",
      );
      expect(dispatcher).not.toContain('process.env.NODE_ENV === "production"');
      expect(dispatcher).toContain("await assertExactDatabasePrincipal({");
    }
  });

  it("hard-forces the production and disposable-QA profiles in Compose", () => {
    expect(compose).toContain(
      "NODE_ENV: production\n      QUILLMD_SERVICE_ROLE: meddoc-pro-app",
    );
    expect(compose).toContain(
      "NODE_ENV: production\n      QUILLMD_SERVICE_ROLE: transcribe-md-worker",
    );
    expect(qaCompose).toContain(
      "NODE_ENV: production\n      QUILLMD_SERVICE_ROLE: transcribe-md-worker",
    );
    expect(
      compose.match(
        /^      QUILLMD_DATABASE_PRINCIPAL_PROFILE: exact-production-v1$/gmu,
      ),
    ).toHaveLength(7);
    expect(
      qaCompose.match(
        /^      QUILLMD_DATABASE_PRINCIPAL_PROFILE: synthetic-disposable-qa-v1$/gmu,
      ),
    ).toHaveLength(2);
    expect(
      compose.match(/^      QUILLMD_SERVICE_ROLE: transcribe-md-worker$/gmu),
    ).toHaveLength(1);
    expect(
      qaCompose.match(/^      QUILLMD_SERVICE_ROLE: transcribe-md-worker$/gmu),
    ).toHaveLength(1);
    expect(compose).toContain(
      "QUILLMD_AUTH_SESSION_VERIFIER_PROFILE: template-twin-admin-control-v1",
    );
    expect(
      compose.match(/^      QUILLMD_AUTH_SESSION_VERIFIER_PROFILE: ""$/gmu),
    ).toHaveLength(6);
    expect(
      qaCompose.match(/^      QUILLMD_AUTH_SESSION_VERIFIER_PROFILE: ""$/gmu),
    ).toHaveLength(2);
  });

  it("keeps the database-principal census separate from the six-runtime rollback census", () => {
    expect(runtimeCensus).not.toContain('"meddoc-pro"');
    expect(runtimeCensus).toContain('role: "transcribe-md-worker"');
    expect(runtimeCensus).toContain(
      'QUILLMD_DATABASE_PRINCIPAL_PROFILE !== "exact-production-v1"',
    );
    expect(runtimeSwap).toContain(
      'QUILLMD_DATABASE_PRINCIPAL_PROFILE: "exact-production-v1"',
    );
    for (const service of [
      "meddoc-pro",
      "transcribe-md",
      "template-twin-admin-app",
      "template-twin-admin-control",
      "transcribe-md-worker",
      "template-twin-audit-dispatcher",
      "auth-email-dispatcher",
    ]) {
      expect(principalCensus).toContain(`"${service}"`);
    }
    expect(principalCensus).toContain('"meddoc_release_security"');
    expect(principalCensus).toContain('key === "PGUSER"');
    expect(principalCensus).toContain('key === "POSTGRES_USER"');
    expect(humanReleaseWorkflow).toContain(
      "node scripts/database-principal-runtime-census.mjs",
    );
    expect(runtimeSwap).not.toContain("database-principal-runtime-census.mjs");
  });

  it("exports one shared mapping and exact-principal implementation", () => {
    expect(
      Object.keys(QUILLMD_PRODUCTION_RUNTIME_DATABASE_PRINCIPALS),
    ).toHaveLength(7);
    expect(dbPackage).toContain('"./exact-database-principal"');
    expect(dbPackage).toContain('"./production-runtime-principal"');
  });
});
