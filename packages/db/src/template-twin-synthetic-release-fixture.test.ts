import { randomUUID } from "node:crypto";
import {
  chmodSync,
  lstatSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import {
  buildSyntheticRuntimeEnvelope,
  parseSyntheticReleaseFixturePhase,
  serializeSyntheticRuntimeEnvironment,
  SYNTHETIC_RELEASE_DATABASE_PROFILE,
  SYNTHETIC_RELEASE_FIXTURE_ACKNOWLEDGEMENT,
  SYNTHETIC_RELEASE_FIXTURE_PROFILE,
  validateSyntheticReleaseFixtureBoundary,
  writePrivateFileAtomically,
} from "../scripts/template-twin-synthetic-release-fixture";

const temporaryDirectories: string[] = [];
const sourceCommitSha = "a".repeat(40);
const appImageDigest = `sha256:${"b".repeat(64)}`;
const workerImageDigest = `sha256:${"c".repeat(64)}`;
const migratorImageDigest = `sha256:${"d".repeat(64)}`;

function environment(
  overrides: Record<string, string | undefined> = {},
): Record<string, string | undefined> {
  return {
    CI: "true",
    GITHUB_ACTIONS: "true",
    GITHUB_REPOSITORY: "kasrarayat-cloud/MedDoc",
    GITHUB_EVENT_NAME: "pull_request",
    GITHUB_RUN_ID: "123456789",
    GITHUB_RUN_ATTEMPT: "2",
    GITHUB_SHA: "e".repeat(40),
    GITHUB_ENV: "/runner/_runner_file_commands/set_env_contract",
    RUNNER_TEMP: "/runner",
    QUILLMD_SYNTHETIC_CI_RELEASE_FIXTURE:
      SYNTHETIC_RELEASE_FIXTURE_ACKNOWLEDGEMENT,
    QUILLMD_SYNTHETIC_CI_RELEASE_PROFILE: SYNTHETIC_RELEASE_FIXTURE_PROFILE,
    QUILLMD_SYNTHETIC_CI_DATABASE_PROFILE: SYNTHETIC_RELEASE_DATABASE_PROFILE,
    QUILLMD_SYNTHETIC_CI_REPOSITORY_ROOT: "/workspace",
    QUILLMD_SYNTHETIC_CI_EXPECTED_SHA: sourceCommitSha,
    QUILLMD_RELEASE_SHA: sourceCommitSha,
    QA_TRANSCRIBE_MD_IMAGE: appImageDigest,
    QA_TRANSCRIBE_MD_WORKER_IMAGE: workerImageDigest,
    QA_DB_MIGRATE_IMAGE: migratorImageDigest,
    DATABASE_URL:
      "postgresql://meddoc:qa_test_pw@127.0.0.1:5432/meddoc_qa_test?schema=public&options=-c%20search_path%3Dpg_catalog%2Cpublic",
    TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL:
      "postgresql://meddoc_release_control:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@127.0.0.1:5432/meddoc_qa_test?schema=public&options=-c%20search_path%3Dpg_catalog%2Cpublic",
    TEMPLATE_TWIN_SYNTHETIC_RUNTIME_DATABASE_URL:
      "postgresql://meddoc_runtime:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb@127.0.0.1:5432/meddoc_qa_test?schema=public&options=-c%20search_path%3Dpg_catalog%2Cpublic",
    ...overrides,
  };
}

afterEach(() => {
  for (const directory of temporaryDirectories.splice(0)) {
    rmSync(directory, { recursive: true, force: true });
  }
});

describe("Template Twin synthetic release fixture", () => {
  it.each(["prepare", "activate", "replace", "revoke", "cleanup"] as const)(
    "accepts the exact %s lifecycle phase",
    (phase) => {
      expect(parseSyntheticReleaseFixturePhase(["--phase", phase])).toBe(phase);
    },
  );

  it.each([
    [],
    ["prepare"],
    ["--phase", "unknown"],
    ["--phase", "prepare", "extra"],
  ])("rejects malformed phase arguments", (...args) => {
    expect(() => parseSyntheticReleaseFixturePhase(args)).toThrow(
      "TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_PHASE_INVALID",
    );
  });

  it("accepts only the exact disposable GitHub runner boundary", () => {
    const result = validateSyntheticReleaseFixtureBoundary(
      environment(),
      "/workspace",
    );

    expect(result).toMatchObject({
      repositoryRoot: "/workspace",
      runnerRoot: "/runner",
      runId: "123456789",
      runAttempt: "2",
      sourceCommitSha,
      appImageDigest,
      workerImageDigest,
      migratorImageDigest,
    });
    expect(result.outputDirectory).toBe(
      "/runner/quillmd-template-twin-release-fixture-123456789-2",
    );
  });

  it.each([
    [
      "production database",
      {
        DATABASE_URL:
          "postgresql://meddoc:password@127.0.0.1:5432/meddoc?schema=public&options=-c%20search_path%3Dpg_catalog%2Cpublic",
      },
    ],
    [
      "remote database",
      {
        DATABASE_URL:
          "postgresql://meddoc:password@postgres:5432/meddoc_qa_test?schema=public&options=-c%20search_path%3Dpg_catalog%2Cpublic",
      },
    ],
    [
      "wrong principal",
      {
        TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL:
          "postgresql://meddoc:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@127.0.0.1:5432/meddoc_qa_test?schema=public&options=-c%20search_path%3Dpg_catalog%2Cpublic",
      },
    ],
    ["production mode", { NODE_ENV: "production" }],
    [
      "production authority",
      { TEMPLATE_TWIN_LINEAGE_ALLOW_PRODUCTION: "true" },
    ],
    ["synthetic authentication bypass", { AUTH_USE_MOCK: "false" }],
    ["provider credential", { OPENAI_API_KEY: "synthetic-but-forbidden" }],
    ["wrong repository root", { QUILLMD_SYNTHETIC_CI_REPOSITORY_ROOT: "/tmp" }],
    [
      "wrong release SHA",
      { QUILLMD_SYNTHETIC_CI_EXPECTED_SHA: "f".repeat(40) },
    ],
    [
      "mutable image",
      { QA_TRANSCRIBE_MD_IMAGE: "meddoc-pro-transcribe-md:latest" },
    ],
  ])("rejects the %s boundary", (_label, override) => {
    expect(() =>
      validateSyntheticReleaseFixtureBoundary(
        environment(override),
        "/workspace",
      ),
    ).toThrow(/^TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_/u);
  });

  it("binds distinct APP and WORKER envelopes to their exact component images", () => {
    const common = {
      keyId: "synthetic-ci-runtime-123-1",
      signingSecret: Buffer.from("a".repeat(32), "utf8"),
      releaseIdentitySha256: "1".repeat(64),
      sourceCommitSha,
      appImageDigest,
      workerImageDigest,
      issuedAtEpochSeconds: 2_000_000_000,
      expiresAtEpochSeconds: 2_000_003_600,
    } as const;
    const app = buildSyntheticRuntimeEnvelope({
      ...common,
      instanceId: "synthetic-ci-app-123-1",
      component: "APP",
      nonce: randomUUID(),
    });
    const worker = buildSyntheticRuntimeEnvelope({
      ...common,
      instanceId: "synthetic-ci-worker-123-1",
      component: "WORKER",
      nonce: randomUUID(),
    });
    const decode = (value: string) =>
      JSON.parse(Buffer.from(value, "base64url").toString("utf8")) as {
        component: string;
        imageDigest: string;
        instanceId: string;
      };

    expect(app).not.toBe(worker);
    expect(decode(app)).toMatchObject({
      component: "APP",
      imageDigest: appImageDigest,
      instanceId: "synthetic-ci-app-123-1",
    });
    expect(decode(worker)).toMatchObject({
      component: "WORKER",
      imageDigest: workerImageDigest,
      instanceId: "synthetic-ci-worker-123-1",
    });

    const runtimeEnvironment = serializeSyntheticRuntimeEnvironment({
      killSwitch: "true",
      releaseIdentitySha256: "1".repeat(64),
      sourceCommitSha,
      appImageDigest,
      workerImageDigest,
      migratorImageDigest,
      appInstanceId: "synthetic-ci-app-123-1",
      workerInstanceId: "synthetic-ci-worker-123-1",
      appRuntimeAttestation: app,
      workerRuntimeAttestation: worker,
    });
    expect(runtimeEnvironment).toContain(
      `QA_TEMPLATE_TWIN_APP_RUNTIME_ATTESTATION=${app}\n`,
    );
    expect(runtimeEnvironment).toContain(
      `QA_TEMPLATE_TWIN_WORKER_RUNTIME_ATTESTATION=${worker}\n`,
    );
    expect(runtimeEnvironment).toContain("QA_TEMPLATE_TWIN_KILL_SWITCH=true\n");
    expect(runtimeEnvironment).not.toMatch(
      /DATABASE_URL|PASSWORD|SESSION|SIGNING_SECRET/u,
    );

    const enabledRuntimeEnvironment = serializeSyntheticRuntimeEnvironment({
      killSwitch: "false",
      releaseIdentitySha256: "1".repeat(64),
      sourceCommitSha,
      appImageDigest,
      workerImageDigest,
      migratorImageDigest,
      appInstanceId: "synthetic-ci-app-123-1",
      workerInstanceId: "synthetic-ci-worker-123-1",
      appRuntimeAttestation: app,
      workerRuntimeAttestation: worker,
    });
    expect(enabledRuntimeEnvironment).toContain(
      "QA_TEMPLATE_TWIN_KILL_SWITCH=false\n",
    );
  });

  it("publishes private files atomically and refuses replacement", () => {
    const temporaryRoot = mkdtempSync(
      join(tmpdir(), "template-twin-synthetic-fixture-"),
    );
    temporaryDirectories.push(temporaryRoot);
    const output = join(temporaryRoot, "output");
    mkdirSync(output, { mode: 0o700 });
    chmodSync(output, 0o700);

    const destination = writePrivateFileAtomically(
      output,
      "runtime.env",
      "QA_TEMPLATE_TWIN_KILL_SWITCH=false\n",
    );
    expect(readFileSync(destination, "utf8")).toBe(
      "QA_TEMPLATE_TWIN_KILL_SWITCH=false\n",
    );
    expect(lstatSync(destination).mode & 0o777).toBe(0o600);
    expect(lstatSync(destination).uid).toBe(process.getuid?.());
    expect(lstatSync(destination).nlink).toBe(1);
    expect(() =>
      writePrivateFileAtomically(output, "runtime.env", "replacement\n"),
    ).toThrow("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_FILE_EXISTS");
  });
});
