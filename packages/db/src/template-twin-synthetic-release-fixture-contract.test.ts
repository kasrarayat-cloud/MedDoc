import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const repositoryRoot = resolve(import.meta.dirname, "../../..");
const read = (path: string): string =>
  readFileSync(resolve(repositoryRoot, path), "utf8");

const fixture = read(
  "packages/db/scripts/template-twin-synthetic-release-fixture.ts",
);
const databasePackage = JSON.parse(read("packages/db/package.json")) as {
  scripts: Record<string, string>;
};
const dedicatedTypeScript = read(
  "packages/db/tsconfig.synthetic-ci-release.json",
);

describe("Template Twin disposable release fixture source contract", () => {
  it("uses production release control without self-registering runtime receipts", () => {
    expect(fixture).toContain(
      'import("../../../apps/transcribe-md/src/lib/template-twin/release-control")',
    );
    for (const call of [
      "createTemplateTwinReleaseCandidate({",
      "freezeTemplateTwinReleaseCandidate({",
      "recordTemplateTwinReleaseApproval({",
      "activateTemplateTwinReleaseCheckpoint(",
      "revokeTemplateTwinRelease({",
    ]) {
      expect(fixture).toContain(call);
    }
    expect(
      fixture.match(/activateTemplateTwinReleaseCheckpoint\(/gu)?.length,
    ).toBe(1);
    expect(fixture).not.toContain("registerTemplateTwinRuntimeAttestation");
    expect(fixture).not.toContain(
      'import("../../../apps/transcribe-md/src/lib/template-twin/runtime-attestation")',
    );
    expect(fixture).not.toMatch(
      /UPDATE\s+"template_twin_rollout_controls"|SET\s+"templateTwinEnabled"\s*=\s*TRUE/iu,
    );
  });

  it("keeps PREPARE disabled and makes ACTIVATE depend on actual fresh receipts", () => {
    const prepare = fixture.slice(
      fixture.indexOf("async function prepareFixture"),
      fixture.indexOf("async function readReleaseControlState"),
    );
    expect(prepare).toContain('killSwitch: "true"');
    expect(prepare).toContain("template_twin_release_runtime_ready(");
    expect(prepare).toContain("readinessRows[0]?.ready !== false");
    expect(prepare).not.toContain("activateTemplateTwinReleaseCheckpoint");
    expect(prepare).not.toContain("revokeTemplateTwinRelease");
    expect(prepare).not.toContain("registerTemplateTwinRuntimeAttestation");
    for (const status of [
      'status: "SEEDED"',
      'status: "CREATED"',
      'status: "FROZEN"',
      "status: `APPROVAL_${discipline}`",
      'status: "PREPARED"',
    ]) {
      expect(prepare).toContain(status);
    }
    expect(prepare.match(/persistLifecycleCheckpoint\(\{/gu)?.length).toBe(5);

    const activate = fixture.slice(
      fixture.indexOf("async function activateFixture"),
      fixture.indexOf("function readFinalLifecyclePhase"),
    );
    const receipts = activate.indexOf("await assertFreshRuntimeReceipts({");
    const activation = activate.indexOf(
      "await releaseControl.activateTemplateTwinReleaseCheckpoint({",
    );
    expect(receipts).toBeGreaterThan(-1);
    expect(activation).toBeGreaterThan(receipts);
    expect(fixture).toContain(
      'attestation."keyId" = ${input.control.runtimeKeyId}',
    );
    expect(fixture).toContain(
      "${input.control.appRuntimeAttestationNonceSha256}::CHAR(64)",
    );
    expect(fixture).toContain(
      "${input.control.workerRuntimeAttestationNonceSha256}::CHAR(64)",
    );
    expect(fixture).toContain("CURRENT_TIMESTAMP + INTERVAL '30 seconds'");
    expect(fixture).toContain(
      "to_timestamp(${input.control.preparedAtEpochSeconds})",
    );
    expect(activate).toContain('phase: "ACTIVE"');
    expect(activate).toContain('killSwitch: "false"');
  });

  it("supports guarded runtime replacement and idempotent defensive cleanup", () => {
    const replacement = fixture.slice(
      fixture.indexOf("async function prepareReplacementFixture"),
      fixture.indexOf("async function revokeFixture"),
    );
    expect(replacement).toContain(
      'const alreadyPrepared = lifecyclePhase === "REPLACEMENT_PREPARED"',
    );
    expect(replacement).toContain("readPersistedRuntimeKillSwitch(boundary)");
    expect(replacement).toContain('phase: "REPLACEMENT_PREPARED"');
    expect(replacement).toContain('killSwitch: "true"');
    const revoke = replacement.indexOf(
      "await releaseControl.revokeTemplateTwinRelease({",
    );
    const verifyRevoked = replacement.indexOf(
      'revoked.releaseStatus !== "REVOKED"',
    );
    const create = replacement.indexOf(
      "await releaseControl.createTemplateTwinReleaseCandidate({",
    );
    expect(revoke).toBeGreaterThan(-1);
    expect(verifyRevoked).toBeGreaterThan(revoke);
    expect(create).toBeGreaterThan(verifyRevoked);
    expect(replacement).toContain(
      'reasonCode: "SYNTHETIC_CI_FIXTURE_SUPERSEDED"',
    );
    expect(replacement).toContain("releaseWasAlreadyRevoked");
    expect(replacement).toContain("let revoked = before");
    expect(replacement).toContain("if (releaseWasActive)");
    expect(replacement).toContain('const cohort = "STAGING" as const');
    expect(replacement).toContain(
      "releaseOrdinal = active.control.releaseOrdinal + 1",
    );
    expect(replacement).toContain(
      "supersedesReleaseId: active.control.releaseId",
    );
    expect(replacement).toContain("supersededReleases");
    expect(replacement).toContain(
      'INSERT INTO "template_twin_release_attestation_keys"',
    );
    for (const status of [
      'status: "REPLACEMENT_REVOKED"',
      'status: "REPLACEMENT_KEY_CREATED"',
      'status: "REPLACEMENT_CREATED"',
      'status: "REPLACEMENT_FROZEN"',
      "status: `REPLACEMENT_APPROVAL_${discipline}`",
      'status: "REPLACEMENT_PREPARED"',
    ]) {
      expect(replacement).toContain(status);
    }
    expect(replacement.match(/persistLifecycleCheckpoint\(\{/gu)?.length).toBe(
      6,
    );
    expect(replacement).not.toContain("activateTemplateTwinReleaseCheckpoint");
    expect(replacement).not.toContain("registerTemplateTwinRuntimeAttestation");

    expect(fixture).toContain("async function cleanupInterruptedFixture");
    expect(fixture).toContain('status: "PARTIAL_CLEANED"');
    expect(fixture).toContain('reasonCode: "SYNTHETIC_CI_FIXTURE_CLEANUP"');
    expect(fixture).toContain('reasonCode: "SYNTHETIC_CI_FIXTURE_INTERRUPTED"');
    expect(fixture).toContain('AND "revokedAt" IS NULL');
    expect(fixture).toContain("await revokeFixture(boundary)");
  });

  it("recovers the exact activation and revocation file-transition windows", () => {
    expect(fixture).toContain("allowActiveFailClosedRuntimeTransition");
    expect(fixture).toContain("allowPreparedActivatedRuntimeTransition");
    expect(fixture).toContain("enabledRuntimeBeforeFailClosedTransition");
    expect(fixture).toContain("closedRuntimeBeforeActivation");
    expect(fixture).toContain("persistedRuntimeHashValid");
    expect(fixture).toContain("readPersistedRuntimeKillSwitch");
    expect(fixture).toContain(
      'phase === "ACTIVE" && runtimeKillSwitch === "true"',
    );
    expect(fixture).toContain(
      '["PREPARED", "REPLACEMENT_PREPARED"].includes(phase)',
    );
    expect(fixture).toContain(
      "BigInt(active.control.releaseGeneration) + BigInt(1)",
    );
    expect(fixture).toContain(
      "BigInt(active.control.globalGeneration) + BigInt(1)",
    );
  });

  it("pins infrastructure first and staging-only replacement cohorts", () => {
    expect(fixture).toContain("const infrastructurePracticeIds = [");
    expect(fixture).toContain("const stagingPracticeIds = [");
    const prepare = fixture.slice(
      fixture.indexOf("async function prepareFixture"),
      fixture.indexOf("async function readReleaseControlState"),
    );
    expect(prepare).toContain('const cohort = "INFRASTRUCTURE" as const');
    expect(prepare).toContain(
      "const authorizedPracticeIds = cohortPracticeIds(cohort)",
    );
    expect(fixture).toContain("controlLineageIsValid");
    expect(fixture).toContain(
      'control.releaseOrdinal === 1 ? "INFRASTRUCTURE" : "STAGING"',
    );
    expect(fixture).toContain(
      "state.releaseOrdinal !== control.releaseOrdinal",
    );
    expect(fixture).toContain(
      "state.supersedesReleaseId !== control.supersedesReleaseId",
    );
  });

  it("makes synthetic approval and non-production semantics unambiguous", () => {
    expect(fixture).toContain('"synthetic-ci-fixture/not-production-approval"');
    expect(fixture).toContain('productionHumanApprovals: "NOT_EVALUATED"');
    expect(fixture).toContain("SYNTHETIC_APPROVAL_EVIDENCE_LABEL");
    expect(fixture).toContain("sourceRef");
    expect(fixture).not.toContain('productionHumanApprovals: "APPROVED"');
  });

  it("exports only protected paths and a non-secret profile through GITHUB_ENV", () => {
    expect(fixture).toContain("QA_TEMPLATE_TWIN_RUNTIME_ENV_FILE");
    expect(fixture).toContain("QA_TEMPLATE_TWIN_RELEASE_CONTROL_FILE");
    expect(fixture).toContain("QA_TEMPLATE_TWIN_FIXTURE_IDENTITIES_FILE");
    expect(fixture).toContain("QA_TEMPLATE_TWIN_FIXTURE_STATE_FILE");
    const githubExport = fixture.slice(
      fixture.indexOf("const safeGithubEnvironment"),
      fixture.indexOf(
        "appendFileSync(",
        fixture.indexOf("const safeGithubEnvironment"),
      ),
    );
    expect(githubExport).not.toMatch(
      /ATTESTATION|DATABASE_URL|PASSWORD|SESSION|SIGNING|SECRET/u,
    );
    expect(fixture).toContain('"runtime.env"');
    expect(fixture).toContain("QA_TEMPLATE_TWIN_APP_RUNTIME_ATTESTATION");
    expect(fixture).toContain("QA_TEMPLATE_TWIN_WORKER_RUNTIME_ATTESTATION");
  });

  it("uses exact runner, database, principal, image and source guards", () => {
    for (const contract of [
      "assertNonProdDatabase(raw)",
      'const REQUIRED_DATABASE = "meddoc_qa_test"',
      'const REQUIRED_HOST = "127.0.0.1"',
      '"meddoc_release_control"',
      '"meddoc_runtime"',
      "QUILLMD_SYNTHETIC_CI_REPOSITORY_ROOT",
      "GITHUB_RUN_ID",
      "GITHUB_RUN_ATTEMPT",
      "QUILLMD_SYNTHETIC_CI_EXPECTED_SHA",
      "QA_TRANSCRIBE_MD_IMAGE",
      "QA_TRANSCRIBE_MD_WORKER_IMAGE",
      "QA_DB_MIGRATE_IMAGE",
    ]) {
      expect(fixture).toContain(contract);
    }
  });

  it("writes the runtime, control, identity and ready-state files at mode 0600", () => {
    expect(fixture).toContain('openSync(temporary, "wx", 0o600)');
    expect(fixture).toContain("fsyncSync(descriptor)");
    expect(fixture).toContain("renameSync(temporary, destination)");
    expect(fixture).toContain("(metadata.mode & 0o777) !== 0o600");
    expect(fixture).toContain("metadata.uid !== currentProcessUid()");
    expect(fixture).toContain("metadata.nlink !== 1");
    for (const name of [
      '"runtime.env"',
      '"release-control.json"',
      '"fixture-identities.json"',
      '"state.json"',
    ]) {
      expect(fixture).toContain(name);
    }
  });

  it("creates login-capable synthetic doctors but protects their plaintext credentials", () => {
    expect(fixture).toContain('import bcrypt from "bcryptjs"');
    expect(fixture).toContain(
      "await bcrypt.hash(doctorPasswords.infrastructure, 12)",
    );
    expect(fixture).toContain(
      "password: authority.doctorPasswords.infrastructure",
    );
    expect(fixture).toContain('"fixture-identities.json"');
    expect(fixture).not.toMatch(/console\.(?:log|error|warn)/u);
  });

  it("registers a guarded package command and dedicated typecheck census", () => {
    expect(
      databasePackage.scripts["release-control:synthetic-ci-fixture"],
    ).toBe(
      "NODE_OPTIONS=--conditions=react-server tsx --tsconfig ../../apps/transcribe-md/tsconfig.json scripts/template-twin-synthetic-release-fixture.ts",
    );
    expect(dedicatedTypeScript).toContain(
      '"scripts/template-twin-synthetic-release-fixture.ts"',
    );
    expect(dedicatedTypeScript).toContain(
      '"src/template-twin-synthetic-release-fixture.test.ts"',
    );
    expect(dedicatedTypeScript).toContain(
      '"src/template-twin-synthetic-release-fixture-contract.test.ts"',
    );
  });

  it("keeps CLI output fixed and value-safe", () => {
    expect(fixture).toContain(
      'const SAFE_FAILURE = "TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_FAILED"',
    );
    expect(fixture).toContain(
      "process.stdout.write(`${JSON.stringify(SAFE_SUCCESS[phase])}\\n`)",
    );
    expect(fixture).toContain("process.stderr.write(`${SAFE_FAILURE}\\n`)");
    expect(fixture).not.toMatch(/error\.(?:message|stack)/u);
  });
});
