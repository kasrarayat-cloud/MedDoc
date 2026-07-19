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

  it("passes an explicit required epoch, runtime mode, and kill switch to every production app, worker, and control runtime", () => {
    expect(
      compose.match(
        /QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH: template-twin-final-schema-v2/g,
      ),
    ).toHaveLength(3);
    expect(
      compose.match(
        /TEMPLATE_TWIN_RUNTIME_MODE: \$\{TEMPLATE_TWIN_RUNTIME_MODE:-standard\}/g,
      ),
    ).toHaveLength(3);
    expect(
      compose.match(
        /TEMPLATE_TWIN_KILL_SWITCH: \$\{TEMPLATE_TWIN_KILL_SWITCH:-true\}/g,
      ),
    ).toHaveLength(3);
    expect(
      qaCompose.match(
        /QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH: template-twin-final-schema-v2/g,
      ),
    ).toHaveLength(2);
  });

  it("enforces the protocol at the real Next startup hook without dropping Sentry", () => {
    expect(instrumentation).toContain("assertQuillmdRuntimeProtocol(process.env)");
    expect(instrumentation).toContain('import("../sentry.server.config")');
    expect(instrumentation).toContain('import("../sentry.edge.config")');
    expect(a11yWorkflow).toContain(
      "QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH: template-twin-final-schema-v2",
    );
  });

  it("rejects both exact pre-stack images and verifies drain/revoke state before swap", () => {
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
    expect(swapGuard).toContain('TRANSCRIBE_MD_IMAGE="$app_id"');
    expect(swapGuard).toContain('TRANSCRIBE_MD_WORKER_IMAGE="$worker_id"');
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
      "The only supported application rollback is a reviewed image built from current",
    );
    expect(runbook).toContain("not a database bypass or a down migration");
    expect(runbook).toContain("not claimed to be a");
    expect(runbook).toContain("host/cluster admission allowlist");
    expect(runbook).toMatch(/Do not fall back to\s+a pre-stack image/);
  });
});
