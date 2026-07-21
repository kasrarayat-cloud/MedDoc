import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import { describe, expect, it } from "vitest";

const repositoryRoot = resolve(import.meta.dirname, "../../../..");
const workflow = readFileSync(
  resolve(repositoryRoot, ".github/workflows/e2e.yml"),
  "utf8",
);
const orchestratorPath = resolve(
  repositoryRoot,
  "scripts/template-twin-synthetic-ci-orchestrator.sh",
);
const orchestrator = readFileSync(orchestratorPath, "utf8");

function ordered(source: string, markers: readonly string[]): void {
  let cursor = -1;
  for (const marker of markers) {
    const next = source.indexOf(marker, cursor + 1);
    expect(next, `missing or out-of-order marker: ${marker}`).toBeGreaterThan(
      cursor,
    );
    cursor = next;
  }
}

describe("Template Twin synthetic CI release orchestration", () => {
  it.each([
    "QA_TEMPLATE_TWIN_KILL_SWITCH",
    "QA_TEMPLATE_TWIN_APP_RUNTIME_ATTESTATION",
    "AUTH_USE_MOCK",
    "MOCK_AI_CALLS",
    "COMPOSE_PROJECT_NAME",
    "DOCKER_HOST",
    "DOCKER_CONFIG",
  ])("rejects an ambient %s before Docker is consulted", (name) => {
    const runnerRoot = mkdtempSync(join(tmpdir(), "quillmd-orchestrator-"));
    const githubEnvironment = join(runnerRoot, "set_env_contract");
    writeFileSync(githubEnvironment, "", { mode: 0o600 });
    try {
      const result = spawnSync(orchestratorPath, ["assert-runtime"], {
        encoding: "utf8",
        env: {
          PATH: process.env.PATH,
          NODE_ENV: "test",
          CI: "true",
          GITHUB_ACTIONS: "true",
          GITHUB_REPOSITORY: "kasrarayat-cloud/MedDoc",
          GITHUB_EVENT_NAME: "pull_request",
          GITHUB_RUN_ID: "123456789",
          GITHUB_RUN_ATTEMPT: "1",
          GITHUB_SHA: "a".repeat(40),
          GITHUB_ENV: githubEnvironment,
          RUNNER_TEMP: runnerRoot,
          QUILLMD_RELEASE_SHA: "b".repeat(40),
          QA_TRANSCRIBE_MD_IMAGE: `sha256:${"c".repeat(64)}`,
          QA_TRANSCRIBE_MD_WORKER_IMAGE: `sha256:${"d".repeat(64)}`,
          QA_DB_MIGRATE_IMAGE: `sha256:${"e".repeat(64)}`,
          QA_DB_RELEASE_CONTROL_PASSWORD: "f".repeat(43),
          QA_DB_RUNTIME_PASSWORD: "g".repeat(43),
          [name]: "unexpected",
        },
      });
      expect(result.status).not.toBe(0);
      expect(result.stdout).toBe("");
      expect(result.stderr).toBe(
        "TEMPLATE_TWIN_SYNTHETIC_CI_ORCHESTRATION_FAILED\n",
      );
    } finally {
      rmSync(runnerRoot, { recursive: true, force: true });
    }
  });

  it("keeps ordinary Chromium on the committed fail-closed baseline", () => {
    const ordinaryStart = workflow.indexOf(
      "Run E2E (chromium; scenario 5 note-format UN-GATED via NOTE_FORMAT_E2E)",
    );
    const releasePrepare = workflow.indexOf(
      "Prepare the disabled synthetic Template Twin release",
    );
    expect(ordinaryStart).toBeGreaterThan(0);
    expect(releasePrepare).toBeGreaterThan(ordinaryStart);
    const ordinaryBoundary = workflow.slice(ordinaryStart, releasePrepare);
    expect(ordinaryBoundary).not.toContain("--env-file");
    expect(ordinaryBoundary).not.toContain("MOCK_TEMPLATE_TWIN_E2E=true");
    expect(ordinaryBoundary).toContain(
      "template-twin-synthetic-ci-orchestrator.sh assert-runtime",
    );
  });

  it("orders disabled registration, activation-capable journeys, and immutable replacement", () => {
    ordered(workflow, [
      "Prepare the disabled synthetic Template Twin release",
      "Start attested Template Twin runtimes with kill switch active",
      "Run E2E (Template Twin infrastructure path)",
      "Verify app + worker after Template Twin infrastructure",
      "Prepare disabled replacement for Template Twin staging QA",
      "Run E2E (authenticated Template Twin staging UI)",
      "Verify app + worker after Template Twin staging UI",
      "Revoke the synthetic Template Twin release after staging",
      "Clean the synthetic Template Twin release fixture after staging",
    ]);
    expect(
      workflow.match(/TEMPLATE_TWIN_SYNTHETIC_CI_ACTIVATE_ACTION:/gu),
    ).toHaveLength(2);
    expect(
      workflow.match(/TEMPLATE_TWIN_SYNTHETIC_CI_REPLACE_ACTION:/gu),
    ).toHaveLength(1);
    const infrastructureJourney = workflow.slice(
      workflow.indexOf("Run E2E (Template Twin infrastructure path)"),
      workflow.indexOf(
        "Verify app + worker after Template Twin infrastructure",
      ),
    );
    expect(infrastructureJourney).toContain(
      "TEMPLATE_TWIN_SYNTHETIC_CI_ACTIVATE_ACTION: activate-cycle",
    );
    expect(infrastructureJourney).not.toContain(
      "TEMPLATE_TWIN_SYNTHETIC_CI_REPLACE_ACTION",
    );
    expect(workflow).toContain("synthetic-ci-fixture/not-production-approval");
    expect(workflow).toContain("do not\n      # represent Desktop Word");
  });

  it("runs the real phased CLI as the host uid and gid with only two exact binds", () => {
    expect(orchestrator).toContain("prepare|activate|replace|revoke|cleanup");
    expect(orchestrator).toContain(
      "release-control:synthetic-ci-fixture -w @meddoc/db -- --phase",
    );
    expect(orchestrator).toContain('--user "$host_uid:$host_gid"');
    expect(orchestrator.match(/--volume /gu)).toHaveLength(2);
    expect(orchestrator).toContain('--volume "$root:$root:rw"');
    expect(orchestrator).toContain(
      '--volume "$host_github_environment:$github_environment_target:rw"',
    );

    const containerInvocation = orchestrator.slice(
      orchestrator.indexOf('docker compose -f "$COMPOSE_FILE" run'),
      orchestrator.indexOf('RUNNER_TEMP="$host_runner_temp"'),
    );
    expect(containerInvocation).not.toContain("postgresql://");
    expect(containerInvocation).not.toMatch(/(?:-e|--env)\s+[A-Z][A-Z0-9_]*=/u);
    expect(containerInvocation).not.toMatch(/\$QA_DB_.*PASSWORD/u);
  });

  it("uses a protected runner root and validates the single mode-0600 runtime file", () => {
    expect(orchestrator).toContain("install -d -m 0700");
    expect(orchestrator).toContain("stat -c '%a' -- \"$directory\"");
    expect(orchestrator).toContain("stat -c '%a' -- \"$file\"");
    expect(orchestrator).toContain("stat -c '%u:%h:%s' -- \"$file\"");
    expect(orchestrator).toContain(
      '[[ "$file" == "$(fixture_output_directory)/runtime.env" ]]',
    );
    expect(orchestrator).toContain("seen[name]++ != 0");
    expect(orchestrator).toContain("if (count != 13) exit 1");
    expect(orchestrator).toContain('== "600"');
    expect(orchestrator).toContain(
      'grep -Fqx -- "QA_TEMPLATE_TWIN_KILL_SWITCH=$expected_switch"',
    );
    expect(orchestrator).toContain(
      "/^QA_TEMPLATE_TWIN_KILL_SWITCH=(true|false)$/",
    );
    expect(orchestrator).toContain(
      "QA_TEMPLATE_TWIN_RUNTIME_ENV_VERSION=template-twin-synthetic-runtime-env-v1",
    );
    expect(orchestrator).toContain(
      "QA_TEMPLATE_TWIN_RELEASE_PROFILE=synthetic-ci-fixture/not-production",
    );
    expect(orchestrator).not.toMatch(/(?:echo|printf).*RUNTIME_ATTESTATION/u);
    expect(orchestrator).not.toMatch(/>>\s*"?\$GITHUB_ENV/u);
  });

  it("refuses shell-precedence auth and rollout overrides before Compose", () => {
    for (const name of [
      "QA_TEMPLATE_TWIN_KILL_SWITCH",
      "QA_TEMPLATE_TWIN_RELEASE_IDENTITY_SHA256",
      "QA_TEMPLATE_TWIN_APP_RUNTIME_ATTESTATION",
      "QA_TEMPLATE_TWIN_WORKER_RUNTIME_ATTESTATION",
      "AUTH_USE_MOCK",
      "MOCK_AI_CALLS",
      "MOCK_TEMPLATE_TWIN_E2E",
      "TEMPLATE_TWIN_STAGING_QA_ENABLED",
      "COMPOSE_PROJECT_NAME",
      "DOCKER_HOST",
      "DOCKER_CONFIG",
      "ANTHROPIC_API_KEY",
      "DEEPGRAM_API_KEY",
    ]) {
      expect(orchestrator).toContain(name);
    }
    expect(orchestrator).toContain('[[ -z "${!name+x}" ]] || fail');
    expect(orchestrator).toContain('[[ "$context" == "default" ]] || fail');
    expect(orchestrator).toContain(
      '[[ "$endpoint" == "unix:///var/run/docker.sock" ]] || fail',
    );
    expect(orchestrator.match(/AUTH_USE_MOCK=false \\/gu)).toHaveLength(3);
    expect(orchestrator.match(/MOCK_AI_CALLS=true \\/gu)).toHaveLength(3);
    expect(
      orchestrator.indexOf("assert_no_ambient_runtime_overrides"),
    ).toBeLessThan(
      orchestrator.indexOf('docker compose -f "$COMPOSE_FILE" run'),
    );
  });

  it("proves health, OOM safety, and the exact application memory limit after every project", () => {
    expect(orchestrator).toContain(".State.OOMKilled");
    expect(orchestrator).toContain('[[ "$state" == "running healthy false" ]]');
    expect(orchestrator).toContain('EXPECTED_APP_MEMORY_BYTES="805306368"');
    expect(orchestrator).toContain("{{.HostConfig.Memory}}");
    for (const marker of [
      "after ordinary Chromium",
      "after Template Twin infrastructure",
      "after Template Twin staging UI",
      "after PHI rejection",
      "after Rx safety",
    ]) {
      expect(workflow).toContain(marker);
    }
  });

  it("unpauses only an observed paused replica after the old release is revoked", () => {
    expect(orchestrator).toContain("{{.State.Paused}}");
    expect(orchestrator).toContain('docker unpause "$container"');
    expect(orchestrator).toContain(">/dev/null 2>&1 || fail");
    expect(orchestrator).toContain('2>/dev/null)" || fail');
    expect(orchestrator).toContain('[[ "$after_paused" == "false" ]]');
    const recreateRuntime = orchestrator.slice(
      orchestrator.indexOf("recreate_runtime()"),
      orchestrator.indexOf("runtime_container_has_closed_switch()"),
    );
    ordered(recreateRuntime, [
      'assert_runtime_environment_file "$expected_switch"',
      "unpause_runtime_if_needed transcribe-md",
      "unpause_runtime_if_needed transcribe-md-worker",
      'docker compose --env-file "$runtime_environment"',
    ]);
    const replacementCycle = orchestrator.slice(
      orchestrator.indexOf("replace-cycle)"),
      orchestrator.indexOf("revoke)"),
    );
    ordered(replacementCycle, [
      "assert_transition_profile staging",
      "run_fixture_phase replace",
      "recreate_runtime true",
      "run_fixture_phase activate",
      "recreate_runtime false",
    ]);
  });

  it("validates least-privilege runtime profiles before release mutations", () => {
    const activationCycle = orchestrator.slice(
      orchestrator.indexOf("activate-cycle)"),
      orchestrator.indexOf("replace-disabled)"),
    );
    ordered(activationCycle, [
      "assert_transition_profile any",
      "run_fixture_phase activate",
    ]);
    const disabledReplacement = orchestrator.slice(
      orchestrator.indexOf("replace-disabled)"),
      orchestrator.indexOf("replace-cycle)"),
    );
    ordered(disabledReplacement, [
      "assert_transition_profile staging",
      "run_fixture_phase replace",
    ]);
    expect(orchestrator).toContain('[[ "$actual" == "staging" ]] || fail');
  });

  it("revokes and cleans before volume destruction, then removes only the validated root", () => {
    ordered(workflow, [
      "Revoke any remaining synthetic Template Twin release",
      "Clean any remaining synthetic Template Twin release state",
      "Tear down the qa stack (volumes too)",
      "Remove the protected Template Twin fixture root",
    ]);
    expect(orchestrator).toContain("ensure_closed_runtime");
    const revokeAndCleanup = orchestrator.slice(
      orchestrator.indexOf("revoke)"),
      orchestrator.indexOf("assert-runtime)"),
    );
    expect(revokeAndCleanup).not.toContain(
      "assert_runtime_environment_file true",
    );
    expect(orchestrator).toContain("if runtime_is_healthy; then");
    expect(orchestrator).toContain(
      'app_container="$(runtime_container_id transcribe-md)" || fail',
    );
    expect(orchestrator).toContain(
      'worker_container="$(runtime_container_id transcribe-md-worker)" || fail',
    );
    expect(orchestrator).not.toMatch(/-z "\$\(docker compose[^\n]+ps -a -q/u);
    expect(orchestrator).toContain('"TEMPLATE_TWIN_KILL_SWITCH=true"');
    expect(orchestrator).toContain('find "$root" -depth -delete');
    expect(orchestrator).not.toMatch(/rm\s+-rf/u);
    expect(workflow).not.toMatch(
      /path:\s*.*(?:QA_TEMPLATE_TWIN|quillmd-template-twin-ci-orchestrator)/u,
    );
  });
});
