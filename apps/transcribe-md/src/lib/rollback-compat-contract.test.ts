import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = path.resolve(__dirname, "../../../..");
const appDockerfile = readFileSync(
  path.join(ROOT, "apps/transcribe-md/Dockerfile"),
  "utf8",
);
const workerDockerfile = readFileSync(
  path.join(ROOT, "apps/transcribe-md/Dockerfile.worker"),
  "utf8",
);
const compose = readFileSync(path.join(ROOT, "docker-compose.yml"), "utf8");
const qaCompose = readFileSync(
  path.join(ROOT, "docker-compose.qa.yml"),
  "utf8",
);
const swapGuard = readFileSync(
  path.join(ROOT, "scripts/template-twin-runtime-swap.sh"),
  "utf8",
);
const runtimeCensus = readFileSync(
  path.join(ROOT, "scripts/template-twin-runtime-census.mjs"),
  "utf8",
);
const runbook = readFileSync(
  path.join(ROOT, "docs/runbooks/template-twin-rollback-compat-v2.md"),
  "utf8",
);
const workerSource = readFileSync(
  path.join(ROOT, "apps/transcribe-md/src/worker.ts"),
  "utf8",
);
const instrumentation = readFileSync(
  path.join(ROOT, "apps/transcribe-md/src/instrumentation.ts"),
  "utf8",
);
const auditDispatcher = readFileSync(
  path.join(ROOT, "apps/transcribe-md/src/audit-dispatcher.ts"),
  "utf8",
);
const authEmailDispatcher = readFileSync(
  path.join(ROOT, "apps/transcribe-md/src/auth-email-dispatcher.ts"),
  "utf8",
);
const a11yWorkflow = readFileSync(
  path.join(ROOT, ".github/workflows/a11y.yml"),
  "utf8",
);

describe("rollback compatibility deployment contract", () => {
  it("stamps both runtime components with one final-schema protocol epoch", () => {
    for (const dockerfile of [appDockerfile, workerDockerfile]) {
      expect(dockerfile).toContain(
        'com.quillmd.runtime-protocol-epoch="template-twin-final-schema-v2"',
      );
      expect(dockerfile).toContain(
        'org.opencontainers.image.revision="${QUILLMD_RELEASE_SHA}"',
      );
      expect(dockerfile).toContain(
        "ENV QUILLMD_RUNTIME_PROTOCOL_EPOCH=template-twin-final-schema-v2",
      );
    }
    expect(appDockerfile).toContain(
      'com.quillmd.runtime-component="transcribe-md-app"',
    );
    expect(workerDockerfile).toContain(
      'com.quillmd.runtime-component="transcribe-md-worker"',
    );
  });

  it("passes an explicit required epoch, runtime mode, and kill switch to all six long-lived same-artifact runtimes", () => {
    expect(
      compose.match(
        /QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH: template-twin-final-schema-v2/g,
      ),
    ).toHaveLength(6);
    expect(
      compose.match(
        /TEMPLATE_TWIN_RUNTIME_MODE: \$\{TEMPLATE_TWIN_RUNTIME_MODE:-standard\}/g,
      ),
    ).toHaveLength(6);
    expect(
      compose.match(
        /TEMPLATE_TWIN_KILL_SWITCH: \$\{TEMPLATE_TWIN_KILL_SWITCH:-true\}/g,
      ),
    ).toHaveLength(6);
    expect(
      compose.match(/com\.quillmd\.rollback-runtime-managed: "true"/g),
    ).toHaveLength(6);
    expect(
      qaCompose.match(
        /QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH: template-twin-final-schema-v2/g,
      ),
    ).toHaveLength(2);
  });

  it("starts both dispatcher runtimes behind the protocol guard and honest progress health", () => {
    for (const dispatcher of [auditDispatcher, authEmailDispatcher]) {
      expect(dispatcher).toContain("assertQuillmdRuntimeProtocol(process.env)");
    }
    expect(auditDispatcher).toContain(
      'const HEARTBEAT_PATH = "/tmp/template-twin-audit-dispatcher-heartbeat"',
    );
    expect(auditDispatcher).toMatch(
      /const result = await drainTemplateTwinAuditOutbox\([\s\S]*?\}\);[\s\S]*?await writeHeartbeat\(\);/u,
    );
    expect(authEmailDispatcher).toMatch(
      /const result = await drainAuthEmailOutbox\([\s\S]*?\}\);[\s\S]*?await writeHeartbeat\(\);/u,
    );
    expect(compose).toContain(
      "/tmp/template-twin-audit-dispatcher-heartbeat",
    );
  });

  it("enforces the protocol at the real Next startup hook without dropping Sentry", () => {
    expect(instrumentation).toContain(
      "assertQuillmdRuntimeProtocol(process.env)",
    );
    expect(instrumentation).toContain(
      "assertAuthOriginRuntimeConfiguration(process.env, APP_URL)",
    );
    expect(instrumentation).toContain('import("../sentry.server.config")');
    expect(instrumentation).toContain('import("../sentry.edge.config")');
    expect(a11yWorkflow).toContain(
      "QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH: template-twin-final-schema-v2",
    );
  });

  it("rejects both exact pre-stack images and verifies the six-service drain/revoke state before swap", () => {
    expect(swapGuard).toContain(
      "sha256:95f57158e3fe56acc832793be3f5da972cc1fdc6c3b85166f8387b3a103f1f90",
    );
    expect(swapGuard).toContain(
      "sha256:412dd3157475fd60a77d417a6db6880343d58755aaf76f044be035fba4acf44e",
    );
    expect(swapGuard).toContain("com.quillmd.runtime-protocol-epoch");
    expect(swapGuard).toContain("org.opencontainers.image.revision");
    expect(swapGuard).toContain('lineage_phase" != "CONTRACTED"');
    expect(swapGuard).toContain('enabled_practices" != "0"');
    expect(swapGuard).toContain('active_twin_templates" != "0"');
    expect(swapGuard).toContain('unsettled_twin_provider_work" != "0"');
    expect(swapGuard).toContain('unsettled_twin_visits" != "0"');
    expect(swapGuard).toContain('unsettled_twin_runs" != "0"');
    expect(swapGuard).toContain('queue_active" != "0"');
    expect(swapGuard).toContain('cleanup_queue_active" != "0"');
    expect(swapGuard).toContain(
      "image references must be immutable sha256 IDs or repository digests",
    );
    for (const service of [
      "transcribe-md",
      "template-twin-admin-app",
      "template-twin-admin-control",
      "transcribe-md-worker",
      "template-twin-audit-dispatcher",
      "auth-email-dispatcher",
    ]) {
      expect(swapGuard).toContain(service);
      expect(runtimeCensus).toContain(service);
    }
    expect(swapGuard).toContain("write_state_overlay");
    expect(swapGuard).toContain("--state-dir");
    expect(swapGuard).toContain("state_sha256");
    expect(swapGuard).toContain("migrator=excluded");
    expect(swapGuard).toContain('TEMPLATE_TWIN_RUNTIME_MODE: "%s"');
    expect(swapGuard).toContain(
      'TEMPLATE_TWIN_KILL_SWITCH: "true"',
    );
    expect(swapGuard).not.toMatch(/state_compose=.*db-migrate/u);
    expect(swapGuard).toContain("--no-build --no-deps --force-recreate");
  });

  it("rejects a queued Twin before the worker enters any provider context", () => {
    const runtimeAdmission = workerSource.indexOf(
      "assertTemplateTwinWorkerRuntimeAdmission(",
    );
    const providerContext = workerSource.indexOf(
      "await runWithWorkerSyntheticQaProviderSelection(",
    );
    expect(runtimeAdmission).toBeGreaterThan(-1);
    expect(providerContext).toBeGreaterThan(runtimeAdmission);
  });

  it("disables synthetic QA lifecycle reconciliation in bridge mode", () => {
    expect(workerSource).toMatch(
      /enabled:\s*templateTwinRuntimeEnabled\(process\.env\)\s*&&\s*evaluateTemplateTwinStagingQaGate\(process\.env\)\.allowed/,
    );
    expect(workerSource).toMatch(
      /templateTwinRuntimeEnabled\(process\.env\)\s*&&\s*job\?\.data\.syntheticQaRunId/,
    );
  });

  it("documents bridge-only rollback without claiming a host admission allowlist", () => {
    expect(runbook).toContain(
      "The only supported application rollback is a reviewed app/worker image pair",
    );
    expect(runbook).toContain("not a database bypass or a down migration");
    expect(runbook).toMatch(/not\s+claimed to be a/u);
    expect(runbook).toContain("host/cluster admission allowlist");
    expect(runbook).toMatch(/Do not fall back to\s+a pre-stack image/);
  });
});
