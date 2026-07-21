#!/usr/bin/env tsx

// GitHub Actions-only Template Twin release fixture. This is deliberately a
// real release-control exercise against one exact disposable QA database, not
// a runtime bypass. It creates conspicuously synthetic authorities, records
// four synthetic decisions that are never represented as production human
// approval, and writes distinct APP and WORKER envelopes while the kill switch
// remains on. A separate activation phase accepts only receipts written by the
// real app and worker before invoking the production release-control API.

import assert from "node:assert/strict";
import { createHash, createHmac, randomBytes, randomUUID } from "node:crypto";
import {
  appendFileSync,
  chmodSync,
  closeSync,
  existsSync,
  fsyncSync,
  lstatSync,
  mkdirSync,
  openSync,
  readFileSync,
  realpathSync,
  renameSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import {
  basename,
  dirname,
  isAbsolute,
  join,
  relative,
  resolve,
  sep,
} from "node:path";
import { fileURLToPath } from "node:url";

import { PrismaPg } from "@prisma/adapter-pg";
import { Prisma, PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

import type { TemplateTwinReleaseActor } from "../../../apps/transcribe-md/src/lib/template-twin/release-control";
import {
  TEMPLATE_TWIN_METRIC_DEFINITIONS,
  TEMPLATE_TWIN_RELEASE_DISCIPLINES,
  templateTwinApprovalConfirmation,
  templateTwinCheckpointConfirmation,
  type TemplateTwinGuardrailPolicy,
  type TemplateTwinReleaseDiscipline,
  type TemplateTwinReleaseIdentityEvidence,
  type TemplateTwinRuntimeComponent,
} from "../../../apps/transcribe-md/src/lib/template-twin/release-control-contracts";
import { assertNonProdDatabase } from "../src/db-guard";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(packageRoot, "../..");

export const SYNTHETIC_RELEASE_FIXTURE_ACKNOWLEDGEMENT =
  "isolated-disposable-template-twin-v1" as const;
export const SYNTHETIC_RELEASE_FIXTURE_PROFILE =
  "synthetic-ci-fixture/not-production" as const;
export const SYNTHETIC_RELEASE_DATABASE_PROFILE =
  "owner-release-control-runtime/meddoc-qa-test-v1" as const;
export const SYNTHETIC_APPROVAL_EVIDENCE_LABEL =
  "synthetic-ci-fixture/not-production-approval" as const;

const FIXTURE_VERSION = "template-twin-synthetic-ci-release-fixture-v1";
const RUNTIME_ENV_VERSION = "template-twin-synthetic-runtime-env-v1";
const REQUIRED_DATABASE = "meddoc_qa_test";
const REQUIRED_HOST = "127.0.0.1";
const REQUIRED_PORT = "5432";
const REQUIRED_OPTIONS = "-c search_path=pg_catalog,public";
const SAFE_SUCCESS = Object.freeze({
  prepare: Object.freeze({
    code: "TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_PREPARED",
    profile: SYNTHETIC_RELEASE_FIXTURE_PROFILE,
    productionHumanApprovals: "NOT_EVALUATED",
  }),
  activate: Object.freeze({
    code: "TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_ACTIVATED",
    profile: SYNTHETIC_RELEASE_FIXTURE_PROFILE,
    productionHumanApprovals: "NOT_EVALUATED",
  }),
  replace: Object.freeze({
    code: "TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_REPLACEMENT_PREPARED",
    profile: SYNTHETIC_RELEASE_FIXTURE_PROFILE,
    productionHumanApprovals: "NOT_EVALUATED",
  }),
  revoke: Object.freeze({
    code: "TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_REVOKED",
    profile: SYNTHETIC_RELEASE_FIXTURE_PROFILE,
    productionHumanApprovals: "NOT_EVALUATED",
  }),
  cleanup: Object.freeze({
    code: "TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_CLEANUP_COMPLETE",
    profile: SYNTHETIC_RELEASE_FIXTURE_PROFILE,
    productionHumanApprovals: "NOT_EVALUATED",
  }),
});
const SAFE_FAILURE = "TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_FAILED";
const SHA = /^[a-f0-9]{40}$/u;
const DIGEST = /^sha256:[a-f0-9]{64}$/u;
const UUID =
  /^[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/u;
const INTEGER = /^[1-9][0-9]{0,19}$/u;
const SAFE_SECRET = /^[A-Za-z0-9_-]{8,256}$/u;

const forbiddenAmbientAuthority = [
  "DATABASE_RELEASE_MIGRATION_ALLOW_PRODUCTION",
  "TEMPLATE_TWIN_LINEAGE_ALLOW_PRODUCTION",
  "AUTH_TOKEN_LINEARIZATION_ALLOW_PRODUCTION",
  "OPENAI_API_KEY",
  "ANTHROPIC_API_KEY",
  "DEEPGRAM_API_KEY",
  "RESEND_API_KEY",
  "SENTRY_AUTH_TOKEN",
  "AWS_ACCESS_KEY_ID",
  "AWS_SECRET_ACCESS_KEY",
  "GOOGLE_APPLICATION_CREDENTIALS",
  "MINIO_ACCESS_KEY",
  "MINIO_SECRET_KEY",
  "AUTH_SECRET",
  "NEXTAUTH_SECRET",
  "MFA_SECRET_KEYRING_FILE",
  "QA_AUDITOR_PASSWORD",
  "AUTH_USE_MOCK",
  "MOCK_AI_CALLS",
  "MOCK_TEMPLATE_TWIN_E2E",
  "EMAIL_AUTO_CONFIRM_ALLOW_IN_PROD",
  "RATE_LIMIT_DISABLE_ALLOW_IN_PROD",
] as const;

export const SYNTHETIC_FIXTURE_IDENTITIES = Object.freeze({
  administrator: {
    practiceId: "synthetic_ci_template_twin_release_admin",
    creatorId: "synthetic_ci_template_twin_release_creator",
  },
  infrastructure: {
    practiceId: "synthetic_ci_template_twin_infrastructure",
    doctorId: "synthetic_ci_template_twin_infrastructure_doctor",
    doctorEmail: "template-twin-infrastructure@synthetic.test",
  },
  stagingPrimary: {
    practiceId: "synthetic_ci_template_twin_staging_primary",
    doctorId: "synthetic_ci_template_twin_staging_primary_doctor",
    doctorEmail: "template-twin-staging-primary@synthetic.test",
  },
  stagingForeign: {
    practiceId: "synthetic_ci_template_twin_staging_foreign",
    doctorId: "synthetic_ci_template_twin_staging_foreign_doctor",
    doctorEmail: "template-twin-staging-foreign@synthetic.test",
  },
});

const infrastructurePracticeIds = [
  SYNTHETIC_FIXTURE_IDENTITIES.infrastructure.practiceId,
] as const;

const stagingPracticeIds = [
  SYNTHETIC_FIXTURE_IDENTITIES.stagingPrimary.practiceId,
  SYNTHETIC_FIXTURE_IDENTITIES.stagingForeign.practiceId,
] as const;

const allFixturePracticeIds = [
  SYNTHETIC_FIXTURE_IDENTITIES.infrastructure.practiceId,
  SYNTHETIC_FIXTURE_IDENTITIES.stagingPrimary.practiceId,
  SYNTHETIC_FIXTURE_IDENTITIES.stagingForeign.practiceId,
] as const;

type SyntheticReleaseCohort = "INFRASTRUCTURE" | "STAGING";

type Environment = Readonly<Record<string, string | undefined>>;
export type SyntheticReleaseFixturePhase =
  | "prepare"
  | "activate"
  | "replace"
  | "revoke"
  | "cleanup";

export interface SyntheticReleaseFixtureBoundary {
  readonly repositoryRoot: string;
  readonly runnerRoot: string;
  readonly githubEnvironment: string;
  readonly outputDirectory: string;
  readonly runId: string;
  readonly runAttempt: string;
  readonly sourceCommitSha: string;
  readonly appImageDigest: string;
  readonly workerImageDigest: string;
  readonly migratorImageDigest: string;
  readonly ownerDatabaseUrl: string;
  readonly releaseControlDatabaseUrl: string;
  readonly runtimeDatabaseUrl: string;
}

export interface RuntimeEnvelopeInput {
  readonly keyId: string;
  readonly signingSecret: Uint8Array;
  readonly releaseIdentitySha256: string;
  readonly instanceId: string;
  readonly component: TemplateTwinRuntimeComponent;
  readonly sourceCommitSha: string;
  readonly appImageDigest: string;
  readonly workerImageDigest: string;
  readonly issuedAtEpochSeconds: number;
  readonly expiresAtEpochSeconds: number;
  readonly nonce: string;
}

interface DatabaseIdentity {
  readonly currentUser: string;
  readonly databaseName: string;
}

interface SeededFixtureAuthority {
  readonly creator: TemplateTwinReleaseActor;
  readonly reviewers: ReadonlyMap<
    TemplateTwinReleaseDiscipline,
    TemplateTwinReleaseActor
  >;
  readonly runtimeKeyId: string;
  readonly runtimeSigningSecret: Uint8Array;
  readonly doctorPasswords: {
    readonly infrastructure: string;
    readonly stagingPrimary: string;
    readonly stagingForeign: string;
  };
}

interface SupersededReleaseDocument {
  readonly releaseOrdinal: number;
  readonly cohort: SyntheticReleaseCohort;
  readonly releaseId: string;
  readonly releaseIdentitySha256: string;
  readonly releaseGeneration: string;
  readonly globalGeneration: string;
  readonly appInstanceId: string;
  readonly workerInstanceId: string;
  readonly runtimeKeyId: string;
  readonly status: "REVOKED";
}

function runtimeIdentity(
  boundary: SyntheticReleaseFixtureBoundary,
  releaseOrdinal: number,
): {
  readonly appInstanceId: string;
  readonly workerInstanceId: string;
  readonly runtimeKeyId: string;
} {
  if (
    !Number.isSafeInteger(releaseOrdinal) ||
    releaseOrdinal < 1 ||
    releaseOrdinal > 99
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_ORDINAL_INVALID");
  }
  const suffix = `-${boundary.runId}-${boundary.runAttempt}-r${releaseOrdinal}`;
  return {
    appInstanceId: `synthetic-ci-app${suffix}`,
    workerInstanceId: `synthetic-ci-worker${suffix}`,
    runtimeKeyId: `synthetic-ci-runtime${suffix}`,
  };
}

function cohortPracticeIds(cohort: SyntheticReleaseCohort): readonly string[] {
  return cohort === "INFRASTRUCTURE"
    ? infrastructurePracticeIds
    : stagingPracticeIds;
}

function fail(code: string): never {
  throw new Error(code);
}

function currentProcessUid(): number {
  if (typeof process.getuid !== "function") {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_FILESYSTEM_INVALID");
  }
  return process.getuid();
}

export function parseSyntheticReleaseFixturePhase(
  args: readonly string[],
): SyntheticReleaseFixturePhase {
  if (
    args.length !== 2 ||
    args[0] !== "--phase" ||
    !["prepare", "activate", "replace", "revoke", "cleanup"].includes(
      args[1] ?? "",
    )
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_PHASE_INVALID");
  }
  return args[1] as SyntheticReleaseFixturePhase;
}

function required(environment: Environment, name: string): string {
  const value = environment[name];
  if (!value || /[\r\n]/u.test(value)) {
    fail(`TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_${name}_INVALID`);
  }
  return value;
}

function isWithin(root: string, candidate: string): boolean {
  const path = relative(root, candidate);
  return (
    path !== "" &&
    path !== ".." &&
    !path.startsWith(`..${sep}`) &&
    !isAbsolute(path)
  );
}

function validateDatabaseUrl(
  raw: string,
  expectedUser: "meddoc" | "meddoc_release_control" | "meddoc_runtime",
): void {
  let parsed: URL;
  try {
    assertNonProdDatabase(raw);
    parsed = new URL(raw);
  } catch {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_DATABASE_INVALID");
  }
  const parameterNames = [...parsed.searchParams.keys()].sort();
  if (
    parsed.protocol !== "postgresql:" ||
    parsed.username !== expectedUser ||
    !SAFE_SECRET.test(parsed.password) ||
    parsed.hostname !== REQUIRED_HOST ||
    parsed.port !== REQUIRED_PORT ||
    decodeURIComponent(parsed.pathname) !== `/${REQUIRED_DATABASE}` ||
    parsed.hash !== "" ||
    parameterNames.join("\n") !== "options\nschema" ||
    parsed.searchParams.get("schema") !== "public" ||
    parsed.searchParams.get("options") !== REQUIRED_OPTIONS
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_DATABASE_INVALID");
  }
}

export function validateSyntheticReleaseFixtureBoundary(
  environment: Environment,
  expectedRepositoryRoot: string = repositoryRoot,
): SyntheticReleaseFixtureBoundary {
  if (
    environment.CI !== "true" ||
    environment.GITHUB_ACTIONS !== "true" ||
    environment.GITHUB_REPOSITORY !== "kasrarayat-cloud/MedDoc" ||
    !["pull_request", "push"].includes(environment.GITHUB_EVENT_NAME ?? "") ||
    environment.QUILLMD_SYNTHETIC_CI_RELEASE_FIXTURE !==
      SYNTHETIC_RELEASE_FIXTURE_ACKNOWLEDGEMENT ||
    environment.QUILLMD_SYNTHETIC_CI_RELEASE_PROFILE !==
      SYNTHETIC_RELEASE_FIXTURE_PROFILE ||
    environment.QUILLMD_SYNTHETIC_CI_DATABASE_PROFILE !==
      SYNTHETIC_RELEASE_DATABASE_PROFILE ||
    environment.NODE_ENV === "production" ||
    environment.QUILLMD_SERVICE_ROLE !== undefined
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_BOUNDARY_REQUIRED");
  }
  for (const name of forbiddenAmbientAuthority) {
    if (environment[name] !== undefined) {
      fail(
        "TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_AMBIENT_AUTHORITY_REFUSED",
      );
    }
  }

  const configuredRoot = required(
    environment,
    "QUILLMD_SYNTHETIC_CI_REPOSITORY_ROOT",
  );
  const exactRepositoryRoot = resolve(expectedRepositoryRoot);
  if (
    !isAbsolute(configuredRoot) ||
    resolve(configuredRoot) !== exactRepositoryRoot
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_ROOT_INVALID");
  }

  const runnerRoot = required(environment, "RUNNER_TEMP");
  const githubEnvironment = required(environment, "GITHUB_ENV");
  const runId = required(environment, "GITHUB_RUN_ID");
  const runAttempt = required(environment, "GITHUB_RUN_ATTEMPT");
  if (
    !isAbsolute(runnerRoot) ||
    !isAbsolute(githubEnvironment) ||
    !INTEGER.test(runId) ||
    !INTEGER.test(runAttempt) ||
    !isWithin(runnerRoot, githubEnvironment) ||
    dirname(resolve(githubEnvironment)) !==
      join(resolve(runnerRoot), "_runner_file_commands") ||
    !/^set_env_[A-Za-z0-9_-]{1,128}$/u.test(basename(githubEnvironment))
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_RUN_INVALID");
  }

  const sourceCommitSha = required(environment, "QUILLMD_RELEASE_SHA");
  const githubSha = required(environment, "GITHUB_SHA");
  const expectedSourceCommitSha = required(
    environment,
    "QUILLMD_SYNTHETIC_CI_EXPECTED_SHA",
  );
  if (
    !SHA.test(sourceCommitSha) ||
    !SHA.test(githubSha) ||
    expectedSourceCommitSha !== sourceCommitSha ||
    (environment.GITHUB_EVENT_NAME === "push" && githubSha !== sourceCommitSha)
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_SHA_INVALID");
  }

  const appImageDigest = required(environment, "QA_TRANSCRIBE_MD_IMAGE");
  const workerImageDigest = required(
    environment,
    "QA_TRANSCRIBE_MD_WORKER_IMAGE",
  );
  const migratorImageDigest = required(environment, "QA_DB_MIGRATE_IMAGE");
  if (
    !DIGEST.test(appImageDigest) ||
    !DIGEST.test(workerImageDigest) ||
    !DIGEST.test(migratorImageDigest) ||
    appImageDigest === workerImageDigest
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_IMAGE_INVALID");
  }

  const ownerDatabaseUrl = required(environment, "DATABASE_URL");
  const releaseControlDatabaseUrl = required(
    environment,
    "TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL",
  );
  const runtimeDatabaseUrl = required(
    environment,
    "TEMPLATE_TWIN_SYNTHETIC_RUNTIME_DATABASE_URL",
  );
  validateDatabaseUrl(ownerDatabaseUrl, "meddoc");
  validateDatabaseUrl(releaseControlDatabaseUrl, "meddoc_release_control");
  validateDatabaseUrl(runtimeDatabaseUrl, "meddoc_runtime");

  return {
    repositoryRoot: exactRepositoryRoot,
    runnerRoot: resolve(runnerRoot),
    githubEnvironment: resolve(githubEnvironment),
    outputDirectory: join(
      resolve(runnerRoot),
      `quillmd-template-twin-release-fixture-${runId}-${runAttempt}`,
    ),
    runId,
    runAttempt,
    sourceCommitSha,
    appImageDigest,
    workerImageDigest,
    migratorImageDigest,
    ownerDatabaseUrl,
    releaseControlDatabaseUrl,
    runtimeDatabaseUrl,
  };
}

function assertFilesystemBoundary(
  boundary: SyntheticReleaseFixtureBoundary,
  phase: SyntheticReleaseFixturePhase,
): void {
  let actualRepositoryRoot: string;
  let actualRunnerRoot: string;
  let actualGithubEnvironment: string;
  try {
    actualRepositoryRoot = realpathSync(boundary.repositoryRoot);
    actualRunnerRoot = realpathSync(boundary.runnerRoot);
    actualGithubEnvironment = realpathSync(boundary.githubEnvironment);
  } catch {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_FILESYSTEM_INVALID");
  }
  if (
    actualRepositoryRoot !== boundary.repositoryRoot ||
    actualRunnerRoot !== boundary.runnerRoot ||
    actualGithubEnvironment !== boundary.githubEnvironment ||
    !isWithin(actualRunnerRoot, actualGithubEnvironment) ||
    (phase === "prepare" && existsSync(boundary.outputDirectory)) ||
    (phase !== "prepare" && !existsSync(boundary.outputDirectory))
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_FILESYSTEM_INVALID");
  }
  const runnerMetadata = lstatSync(boundary.runnerRoot);
  const githubEnvironmentMetadata = lstatSync(boundary.githubEnvironment);
  const expectedUid = currentProcessUid();
  if (
    !runnerMetadata.isDirectory() ||
    runnerMetadata.isSymbolicLink() ||
    runnerMetadata.uid !== expectedUid ||
    !githubEnvironmentMetadata.isFile() ||
    githubEnvironmentMetadata.isSymbolicLink() ||
    githubEnvironmentMetadata.uid !== expectedUid ||
    githubEnvironmentMetadata.nlink !== 1
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_FILESYSTEM_INVALID");
  }
  if (phase !== "prepare") {
    const outputMetadata = lstatSync(boundary.outputDirectory);
    if (
      !outputMetadata.isDirectory() ||
      outputMetadata.isSymbolicLink() ||
      (outputMetadata.mode & 0o777) !== 0o700 ||
      outputMetadata.uid !== expectedUid
    ) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_FILESYSTEM_INVALID");
    }
  }
}

function sha256(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function syntheticEvidence(
  boundary: SyntheticReleaseFixtureBoundary,
): TemplateTwinReleaseIdentityEvidence {
  const evidence = (kind: string) =>
    sha256(
      `${SYNTHETIC_RELEASE_FIXTURE_PROFILE}\n${kind}\n${boundary.runId}\n${boundary.runAttempt}\n${boundary.sourceCommitSha}`,
    );
  return {
    sourceCommitSha: boundary.sourceCommitSha,
    baseCommitSha: boundary.sourceCommitSha,
    appImageDigest: boundary.appImageDigest,
    workerImageDigest: boundary.workerImageDigest,
    migratorImageDigest: boundary.migratorImageDigest,
    testCensusEvidenceSha256: evidence("synthetic-test-census"),
    independentReviewEvidenceSha256: evidence("not-production-review"),
    securityEvidenceSha256: evidence("synthetic-security-gate"),
    migrationRestoreEvidenceSha256: evidence("disposable-migration-only"),
    officeWordEvidenceSha256: evidence("not-desktop-word-approval"),
  };
}

function syntheticGuardrailPolicy(): TemplateTwinGuardrailPolicy {
  const stages = {
    CANARY: 1,
    PERCENT_10: 1,
    PERCENT_25: 1,
    PERCENT_50: 1,
    PERCENT_100: 1,
  } as const;
  return {
    schemaVersion: "template-twin-guardrails-v1",
    maxObservationAgeSeconds: 3_600,
    minimumBakeSecondsByStage: stages,
    minimumSampleCountByStage: stages,
    metrics: Object.fromEntries(
      Object.entries(TEMPLATE_TWIN_METRIC_DEFINITIONS).map(
        ([key, definition]) => [
          key,
          {
            direction: definition.direction,
            threshold:
              definition.direction === "MAX" ? definition.min : definition.max,
            critical: [
              "unsafe_bypass_attempt_count",
              "provider_ambiguous_outcome_count",
              "critical_field_accuracy",
              "hallucination_rate",
              "evidence_anchor_validity",
              "exact_dropdown_accuracy",
              "negation_accuracy",
              "laterality_accuracy",
              "table_placement_accuracy",
            ].includes(key),
          },
        ],
      ),
    ) as unknown as TemplateTwinGuardrailPolicy["metrics"],
  };
}

export function buildSyntheticRuntimeEnvelope(
  input: RuntimeEnvelopeInput,
): string {
  const imageDigest =
    input.component === "APP" ? input.appImageDigest : input.workerImageDigest;
  const message = [
    "template-twin-runtime-attestation-v1",
    input.keyId,
    input.nonce,
    input.releaseIdentitySha256,
    input.instanceId,
    input.component,
    input.sourceCommitSha,
    imageDigest,
    String(input.issuedAtEpochSeconds),
    String(input.expiresAtEpochSeconds),
  ].join("\n");
  const envelope = {
    version: "template-twin-runtime-attestation-v1",
    keyId: input.keyId,
    nonce: input.nonce,
    releaseIdentitySha256: input.releaseIdentitySha256,
    instanceId: input.instanceId,
    component: input.component,
    sourceCommitSha: input.sourceCommitSha,
    imageDigest,
    issuedAtEpochSeconds: input.issuedAtEpochSeconds,
    expiresAtEpochSeconds: input.expiresAtEpochSeconds,
    signature: createHmac("sha256", input.signingSecret)
      .update(message)
      .digest("hex"),
  };
  return Buffer.from(JSON.stringify(envelope), "utf8").toString("base64url");
}

export function serializeSyntheticRuntimeEnvironment(input: {
  readonly killSwitch: "true" | "false";
  readonly releaseIdentitySha256: string;
  readonly sourceCommitSha: string;
  readonly appImageDigest: string;
  readonly workerImageDigest: string;
  readonly migratorImageDigest: string;
  readonly appInstanceId: string;
  readonly workerInstanceId: string;
  readonly appRuntimeAttestation: string;
  readonly workerRuntimeAttestation: string;
}): string {
  const values = {
    QA_TEMPLATE_TWIN_RUNTIME_ENV_VERSION: RUNTIME_ENV_VERSION,
    QA_TEMPLATE_TWIN_RELEASE_PROFILE: SYNTHETIC_RELEASE_FIXTURE_PROFILE,
    QA_TEMPLATE_TWIN_KILL_SWITCH: input.killSwitch,
    QA_TEMPLATE_TWIN_RUNTIME_MODE: "standard",
    QA_TEMPLATE_TWIN_RELEASE_IDENTITY_SHA256: input.releaseIdentitySha256,
    QA_TEMPLATE_TWIN_RELEASE_COMMIT_SHA: input.sourceCommitSha,
    QA_TEMPLATE_TWIN_APP_IMAGE_DIGEST: input.appImageDigest,
    QA_TEMPLATE_TWIN_WORKER_IMAGE_DIGEST: input.workerImageDigest,
    QA_TEMPLATE_TWIN_MIGRATOR_IMAGE_DIGEST: input.migratorImageDigest,
    QA_TEMPLATE_TWIN_APP_INSTANCE_ID: input.appInstanceId,
    QA_TEMPLATE_TWIN_WORKER_INSTANCE_ID: input.workerInstanceId,
    QA_TEMPLATE_TWIN_APP_RUNTIME_ATTESTATION: input.appRuntimeAttestation,
    QA_TEMPLATE_TWIN_WORKER_RUNTIME_ATTESTATION: input.workerRuntimeAttestation,
  } as const;
  for (const [name, value] of Object.entries(values)) {
    if (!/^[A-Z][A-Z0-9_]{1,100}$/u.test(name) || /[\r\n]/u.test(value)) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_RUNTIME_ENV_INVALID");
    }
  }
  return `${Object.entries(values)
    .map(([name, value]) => `${name}=${value}`)
    .join("\n")}\n`;
}

export function writePrivateFileAtomically(
  outputDirectory: string,
  fileName: string,
  contents: string,
): string {
  if (!/^[a-z0-9][a-z0-9.-]{1,80}$/u.test(fileName)) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_FILE_NAME_INVALID");
  }
  const destination = join(outputDirectory, fileName);
  if (existsSync(destination)) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_FILE_EXISTS");
  }
  const temporary = join(
    outputDirectory,
    `.${fileName}.${randomBytes(8).toString("hex")}.tmp`,
  );
  let descriptor: number | undefined;
  try {
    descriptor = openSync(temporary, "wx", 0o600);
    writeFileSync(descriptor, contents, { encoding: "utf8" });
    fsyncSync(descriptor);
    closeSync(descriptor);
    descriptor = undefined;
    chmodSync(temporary, 0o600);
    renameSync(temporary, destination);
  } catch {
    if (descriptor !== undefined) closeSync(descriptor);
    if (existsSync(temporary)) unlinkSync(temporary);
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_FILE_WRITE_FAILED");
  }
  const metadata = lstatSync(destination);
  if (
    !metadata.isFile() ||
    metadata.isSymbolicLink() ||
    (metadata.mode & 0o777) !== 0o600 ||
    metadata.uid !== currentProcessUid() ||
    metadata.nlink !== 1
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_FILE_MODE_INVALID");
  }
  return destination;
}

async function assertDatabaseIdentity(
  client: PrismaClient,
  expectedUser: string,
): Promise<void> {
  const rows = await client.$queryRaw<DatabaseIdentity[]>(Prisma.sql`
    SELECT current_user AS "currentUser",
      current_database() AS "databaseName"
  `);
  if (
    rows.length !== 1 ||
    rows[0]?.currentUser !== expectedUser ||
    rows[0]?.databaseName !== REQUIRED_DATABASE
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_PRINCIPAL_INVALID");
  }
}

async function seedFixtureAuthority(input: {
  readonly owner: PrismaClient;
  readonly boundary: SyntheticReleaseFixtureBoundary;
}): Promise<SeededFixtureAuthority> {
  const runtimeSigningSecret = randomBytes(32);
  const runtimeKeyId = runtimeIdentity(input.boundary, 1).runtimeKeyId;
  if (runtimeKeyId.length > 79) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_RUN_INVALID");
  }
  const creatorSession = randomBytes(32).toString("base64url");
  const doctorPasswords = {
    infrastructure: `${randomBytes(24).toString("base64url")}Aa1!`,
    stagingPrimary: `${randomBytes(24).toString("base64url")}Aa1!`,
    stagingForeign: `${randomBytes(24).toString("base64url")}Aa1!`,
  } as const;
  const doctorPasswordHashes = {
    infrastructure: await bcrypt.hash(doctorPasswords.infrastructure, 12),
    stagingPrimary: await bcrypt.hash(doctorPasswords.stagingPrimary, 12),
    stagingForeign: await bcrypt.hash(doctorPasswords.stagingForeign, 12),
  } as const;
  const reviewerSessions = new Map<TemplateTwinReleaseDiscipline, string>(
    TEMPLATE_TWIN_RELEASE_DISCIPLINES.map((discipline) => [
      discipline,
      randomBytes(32).toString("base64url"),
    ]),
  );
  const reviewerIds = new Map<TemplateTwinReleaseDiscipline, string>(
    TEMPLATE_TWIN_RELEASE_DISCIPLINES.map((discipline) => [
      discipline,
      `synthetic_ci_template_twin_reviewer_${discipline.toLowerCase()}`,
    ]),
  );
  const reservedPracticeIds = [
    SYNTHETIC_FIXTURE_IDENTITIES.administrator.practiceId,
    ...allFixturePracticeIds,
  ];
  const reservedUserIds = [
    SYNTHETIC_FIXTURE_IDENTITIES.administrator.creatorId,
    SYNTHETIC_FIXTURE_IDENTITIES.infrastructure.doctorId,
    SYNTHETIC_FIXTURE_IDENTITIES.stagingPrimary.doctorId,
    SYNTHETIC_FIXTURE_IDENTITIES.stagingForeign.doctorId,
    ...reviewerIds.values(),
  ];
  const now = Date.now();

  await input.owner.$transaction(async (tx) => {
    const [globalRows, lineageRows, practiceRows, userRows, releaseRows] =
      await Promise.all([
        tx.$queryRaw<
          Array<{
            enabled: boolean;
            rollbackFenceState: string;
            rollbackOperationId: string | null;
          }>
        >(Prisma.sql`
          SELECT "enabled", "rollbackFenceState", "rollbackOperationId"
          FROM "template_twin_rollout_controls" WHERE "id" = 'global'
          FOR UPDATE
        `),
        tx.$queryRaw<Array<{ phase: string }>>(Prisma.sql`
          SELECT "phase" FROM "template_twin_lineage_migration_progress"
          WHERE "operationKey" = 'note_templates_lineage_v1'
        `),
        tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
          SELECT "id" FROM "practices"
          WHERE "id" IN (${Prisma.join(reservedPracticeIds)})
        `),
        tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
          SELECT "id" FROM "users"
          WHERE "id" IN (${Prisma.join(reservedUserIds)})
        `),
        tx.$queryRaw<Array<{ count: bigint }>>(Prisma.sql`
          SELECT COUNT(*)::BIGINT AS "count"
          FROM "template_twin_release_candidates"
        `),
      ]);
    const global = globalRows[0];
    if (
      !global ||
      global.enabled ||
      global.rollbackFenceState !== "OPEN" ||
      global.rollbackOperationId !== null ||
      lineageRows[0]?.phase !== "CONTRACTED" ||
      practiceRows.length !== 0 ||
      userRows.length !== 0 ||
      releaseRows[0]?.count !== BigInt(0)
    ) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_DATABASE_NOT_FRESH");
    }

    await tx.practice.createMany({
      data: [
        {
          id: SYNTHETIC_FIXTURE_IDENTITIES.administrator.practiceId,
          slug: "synthetic-ci-template-twin-release-admin",
          name: "CI-ONLY Template Twin release administration — NOT PRODUCTION",
          templateTwinEnabled: false,
        },
        {
          id: SYNTHETIC_FIXTURE_IDENTITIES.infrastructure.practiceId,
          slug: "synthetic-ci-template-twin-infrastructure",
          name: "CI-ONLY Template Twin infrastructure practice",
          templateTwinEnabled: false,
        },
        {
          id: SYNTHETIC_FIXTURE_IDENTITIES.stagingPrimary.practiceId,
          slug: "synthetic-ci-template-twin-staging-primary",
          name: "CI-ONLY Template Twin staging primary practice",
          templateTwinEnabled: false,
        },
        {
          id: SYNTHETIC_FIXTURE_IDENTITIES.stagingForeign.practiceId,
          slug: "synthetic-ci-template-twin-staging-foreign",
          name: "CI-ONLY Template Twin staging foreign practice",
          templateTwinEnabled: false,
        },
      ],
    });

    const syntheticAdministratorPasswordHash =
      "synthetic-ci-fixture-password-hash-not-login-capable";
    await tx.user.createMany({
      data: [
        {
          id: SYNTHETIC_FIXTURE_IDENTITIES.infrastructure.doctorId,
          email: SYNTHETIC_FIXTURE_IDENTITIES.infrastructure.doctorEmail,
          passwordHash: doctorPasswordHashes.infrastructure,
          role: "DOCTOR",
          products: ["TRANSCRIBE_MD"],
          practiceId: SYNTHETIC_FIXTURE_IDENTITIES.infrastructure.practiceId,
          emailVerified: new Date(now - 60_000),
        },
        {
          id: SYNTHETIC_FIXTURE_IDENTITIES.stagingPrimary.doctorId,
          email: SYNTHETIC_FIXTURE_IDENTITIES.stagingPrimary.doctorEmail,
          passwordHash: doctorPasswordHashes.stagingPrimary,
          role: "DOCTOR",
          products: ["TRANSCRIBE_MD"],
          practiceId: SYNTHETIC_FIXTURE_IDENTITIES.stagingPrimary.practiceId,
          emailVerified: new Date(now - 60_000),
        },
        {
          id: SYNTHETIC_FIXTURE_IDENTITIES.stagingForeign.doctorId,
          email: SYNTHETIC_FIXTURE_IDENTITIES.stagingForeign.doctorEmail,
          passwordHash: doctorPasswordHashes.stagingForeign,
          role: "DOCTOR",
          products: ["TRANSCRIBE_MD"],
          practiceId: SYNTHETIC_FIXTURE_IDENTITIES.stagingForeign.practiceId,
          emailVerified: new Date(now - 60_000),
        },
        {
          id: SYNTHETIC_FIXTURE_IDENTITIES.administrator.creatorId,
          email: "template-twin-release-creator@synthetic.test",
          passwordHash: syntheticAdministratorPasswordHash,
          role: "ADMIN",
          products: ["SUPER_ADMIN"],
          practiceId: SYNTHETIC_FIXTURE_IDENTITIES.administrator.practiceId,
          emailVerified: new Date(now - 60_000),
          mfaEnabled: true,
          mfaSecret: "synthetic-ci-fixture-mfa-marker-not-a-totp-secret",
          mfaVerifiedAt: new Date(now - 60_000),
        },
        ...TEMPLATE_TWIN_RELEASE_DISCIPLINES.map((discipline) => ({
          id: reviewerIds.get(discipline)!,
          email: `template-twin-reviewer-${discipline.toLowerCase()}@synthetic.test`,
          passwordHash: syntheticAdministratorPasswordHash,
          role: "ADMIN" as const,
          products: ["SUPER_ADMIN" as const],
          practiceId: SYNTHETIC_FIXTURE_IDENTITIES.administrator.practiceId,
          emailVerified: new Date(now - 60_000),
          mfaEnabled: true,
          mfaSecret: "synthetic-ci-fixture-mfa-marker-not-a-totp-secret",
          mfaVerifiedAt: new Date(now - 60_000),
        })),
      ],
    });

    // GitHub-hosted workflows can run for six hours. Keep the synthetic
    // rollback actors and runtime signing key valid beyond that ceiling so an
    // always-run cleanup still has authority at the timeout boundary.
    const expiresAt = new Date(now + 12 * 60 * 60 * 1_000);
    await tx.userSession.createMany({
      data: [
        {
          userId: SYNTHETIC_FIXTURE_IDENTITIES.administrator.creatorId,
          sessionToken: creatorSession,
          expiresAt,
        },
        ...TEMPLATE_TWIN_RELEASE_DISCIPLINES.map((discipline) => ({
          userId: reviewerIds.get(discipline)!,
          sessionToken: reviewerSessions.get(discipline)!,
          expiresAt,
        })),
      ],
    });

    await tx.$executeRaw(Prisma.sql`
      INSERT INTO "template_twin_release_attestation_keys" (
        "keyId", "purpose", "secret", "principalUserId",
        "effectiveAt", "expiresAt"
      ) VALUES (
        ${runtimeKeyId}, 'RUNTIME', ${runtimeSigningSecret}, NULL,
        ${new Date(now - 60_000)}, ${expiresAt}
      )
    `);
    for (const discipline of TEMPLATE_TWIN_RELEASE_DISCIPLINES) {
      await tx.$executeRaw(Prisma.sql`
        INSERT INTO "template_twin_release_authorities" (
          "id", "userId", "discipline", "sourceRef"
        ) VALUES (
          ${randomUUID()}::UUID, ${reviewerIds.get(discipline)!},
          ${discipline}, ${SYNTHETIC_APPROVAL_EVIDENCE_LABEL}
        )
      `);
    }
  });

  return {
    creator: {
      userId: SYNTHETIC_FIXTURE_IDENTITIES.administrator.creatorId,
      sessionId: creatorSession,
    },
    reviewers: new Map(
      TEMPLATE_TWIN_RELEASE_DISCIPLINES.map((discipline) => [
        discipline,
        {
          userId: reviewerIds.get(discipline)!,
          sessionId: reviewerSessions.get(discipline)!,
        },
      ]),
    ),
    runtimeKeyId,
    runtimeSigningSecret,
    doctorPasswords,
  };
}

function client(connectionString: string): PrismaClient {
  return new PrismaClient({
    adapter: new PrismaPg({ connectionString, max: 2 }),
  });
}

interface PreparedControlDocument {
  readonly version: string;
  readonly profile: string;
  readonly phase:
    | "PREPARED"
    | "ACTIVE"
    | "REPLACEMENT_PREPARED"
    | "REVOKED"
    | "CLEANED";
  readonly synthetic: true;
  readonly productionHumanApprovals: "NOT_EVALUATED";
  readonly approvalEvidenceLabel: string;
  readonly runId: string;
  readonly runAttempt: string;
  readonly preparedAtEpochSeconds: number;
  readonly releaseOrdinal: number;
  readonly cohort: SyntheticReleaseCohort;
  readonly authorizedPracticeIds: readonly string[];
  readonly supersedesReleaseId: string | null;
  readonly supersededReleases: readonly SupersededReleaseDocument[];
  readonly releaseId: string;
  readonly releaseIdentitySha256: string;
  readonly sourceCommitSha: string;
  readonly appImageDigest: string;
  readonly workerImageDigest: string;
  readonly migratorImageDigest: string;
  readonly releaseGeneration: string;
  readonly globalGeneration: string;
  readonly appInstanceId: string;
  readonly workerInstanceId: string;
  readonly appRuntimeAttestationNonceSha256: string;
  readonly workerRuntimeAttestationNonceSha256: string;
  readonly runtimeKeyId: string;
  readonly runtimeSigningSecret: string;
  readonly creator: {
    readonly userId: string;
    readonly sessionId: string;
  };
  readonly checkpoint: "CANARY";
  readonly checkpointStatus: "PENDING" | "ACTIVE" | "REVOKED";
}

interface PreparedStateDocument {
  readonly version: string;
  readonly profile: string;
  readonly status:
    | "PREPARED"
    | "ACTIVE"
    | "REPLACEMENT_PREPARED"
    | "REVOKED"
    | "CLEANED";
  readonly productionHumanApprovals: "NOT_EVALUATED";
  readonly releaseOrdinal: number;
  readonly cohort: SyntheticReleaseCohort;
  readonly releaseId: string;
  readonly supersedesReleaseId: string | null;
  readonly files: {
    readonly runtime: { readonly name: string; readonly sha256: string };
    readonly control: { readonly name: string; readonly sha256: string };
    readonly identities: { readonly name: string; readonly sha256: string };
  };
}

interface ReleaseControlStateRow {
  readonly enabled: boolean;
  readonly globalGeneration: bigint;
  readonly releaseStatus: string;
  readonly releaseGeneration: bigint;
  readonly checkpointStatus: string;
}

interface RuntimeReceiptRow {
  readonly component: string;
  readonly instanceId: string;
  readonly imageDigest: string;
  readonly ready: boolean;
}

function jsonDocument(value: unknown): string {
  return `${JSON.stringify(value, null, 2)}\n`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function sameStrings(
  actual: readonly string[],
  expected: readonly string[],
): boolean {
  return (
    actual.length === expected.length &&
    actual.every((value, index) => value === expected[index])
  );
}

function controlLineageIsValid(
  boundary: SyntheticReleaseFixtureBoundary,
  control: PreparedControlDocument,
): boolean {
  if (
    !Number.isSafeInteger(control.releaseOrdinal) ||
    control.releaseOrdinal < 1 ||
    control.releaseOrdinal > 99
  ) {
    return false;
  }
  const expectedCohort: SyntheticReleaseCohort =
    control.releaseOrdinal === 1 ? "INFRASTRUCTURE" : "STAGING";
  const expectedRuntime = runtimeIdentity(boundary, control.releaseOrdinal);
  if (
    control.cohort !== expectedCohort ||
    !Array.isArray(control.authorizedPracticeIds) ||
    !sameStrings(
      control.authorizedPracticeIds,
      cohortPracticeIds(expectedCohort),
    ) ||
    control.appInstanceId !== expectedRuntime.appInstanceId ||
    control.workerInstanceId !== expectedRuntime.workerInstanceId ||
    control.runtimeKeyId !== expectedRuntime.runtimeKeyId ||
    !Array.isArray(control.supersededReleases) ||
    control.supersededReleases.length !== control.releaseOrdinal - 1
  ) {
    return false;
  }
  if (control.releaseOrdinal === 1) {
    return control.supersedesReleaseId === null;
  }
  if (
    control.supersedesReleaseId !==
      control.supersededReleases.at(-1)?.releaseId ||
    control.supersededReleases.some(
      ({ releaseId, releaseIdentitySha256 }) =>
        releaseId === control.releaseId ||
        releaseIdentitySha256 === control.releaseIdentitySha256,
    )
  ) {
    return false;
  }
  const seenReleaseIds = new Set<string>();
  const seenReleaseIdentities = new Set<string>();
  const seenRuntimeKeyIds = new Set<string>();
  return control.supersededReleases.every((release, index) => {
    const ordinal = index + 1;
    const expected = runtimeIdentity(boundary, ordinal);
    const valid =
      release.releaseOrdinal === ordinal &&
      release.cohort === (ordinal === 1 ? "INFRASTRUCTURE" : "STAGING") &&
      UUID.test(release.releaseId) &&
      /^[a-f0-9]{64}$/u.test(release.releaseIdentitySha256) &&
      INTEGER.test(release.releaseGeneration) &&
      INTEGER.test(release.globalGeneration) &&
      release.appInstanceId === expected.appInstanceId &&
      release.workerInstanceId === expected.workerInstanceId &&
      release.runtimeKeyId === expected.runtimeKeyId &&
      release.status === "REVOKED" &&
      !seenReleaseIds.has(release.releaseId) &&
      !seenReleaseIdentities.has(release.releaseIdentitySha256) &&
      !seenRuntimeKeyIds.has(release.runtimeKeyId);
    seenReleaseIds.add(release.releaseId);
    seenReleaseIdentities.add(release.releaseIdentitySha256);
    seenRuntimeKeyIds.add(release.runtimeKeyId);
    return valid;
  });
}

function privateFilePath(
  boundary: SyntheticReleaseFixtureBoundary,
  name:
    | "runtime.env"
    | "release-control.json"
    | "fixture-identities.json"
    | "state.json",
): string {
  return join(boundary.outputDirectory, name);
}

function readPrivateFile(
  boundary: SyntheticReleaseFixtureBoundary,
  name:
    | "runtime.env"
    | "release-control.json"
    | "fixture-identities.json"
    | "state.json",
): string {
  const path = privateFilePath(boundary, name);
  const metadata = lstatSync(path);
  if (
    !metadata.isFile() ||
    metadata.isSymbolicLink() ||
    (metadata.mode & 0o777) !== 0o600 ||
    metadata.uid !== currentProcessUid() ||
    metadata.nlink !== 1 ||
    metadata.size < 2 ||
    metadata.size > 128 * 1_024
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_FILE_MODE_INVALID");
  }
  return readFileSync(path, "utf8");
}

function replacePrivateFileAtomically(
  boundary: SyntheticReleaseFixtureBoundary,
  name: "runtime.env" | "release-control.json" | "state.json",
  contents: string,
): void {
  readPrivateFile(boundary, name);
  const destination = privateFilePath(boundary, name);
  const temporary = join(
    boundary.outputDirectory,
    `.${name}.${randomBytes(8).toString("hex")}.tmp`,
  );
  let descriptor: number | undefined;
  try {
    descriptor = openSync(temporary, "wx", 0o600);
    writeFileSync(descriptor, contents, { encoding: "utf8" });
    fsyncSync(descriptor);
    closeSync(descriptor);
    descriptor = undefined;
    chmodSync(temporary, 0o600);
    renameSync(temporary, destination);
  } catch {
    if (descriptor !== undefined) closeSync(descriptor);
    if (existsSync(temporary)) unlinkSync(temporary);
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_FILE_WRITE_FAILED");
  }
  readPrivateFile(boundary, name);
}

function publishOrReplacePrivateFile(
  boundary: SyntheticReleaseFixtureBoundary,
  name:
    | "runtime.env"
    | "release-control.json"
    | "fixture-identities.json"
    | "state.json",
  contents: string,
): void {
  if (existsSync(privateFilePath(boundary, name))) {
    if (name === "fixture-identities.json") {
      if (readPrivateFile(boundary, name) !== contents) {
        fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_STATE_INVALID");
      }
      return;
    }
    replacePrivateFileAtomically(boundary, name, contents);
    return;
  }
  writePrivateFileAtomically(boundary.outputDirectory, name, contents);
}

function persistLifecycleCheckpoint(input: {
  readonly boundary: SyntheticReleaseFixtureBoundary;
  readonly status: string;
  readonly control: unknown;
  readonly identitiesContents: string;
  readonly runtimeContents?: string;
}): void {
  publishOrReplacePrivateFile(
    input.boundary,
    "fixture-identities.json",
    input.identitiesContents,
  );
  if (input.runtimeContents !== undefined) {
    publishOrReplacePrivateFile(
      input.boundary,
      "runtime.env",
      input.runtimeContents,
    );
  }
  const controlContents = jsonDocument(input.control);
  publishOrReplacePrivateFile(
    input.boundary,
    "release-control.json",
    controlContents,
  );
  const runtimePath = privateFilePath(input.boundary, "runtime.env");
  const files = {
    ...(existsSync(runtimePath)
      ? {
          runtime: {
            name: "runtime.env",
            sha256: sha256(readPrivateFile(input.boundary, "runtime.env")),
          },
        }
      : {}),
    control: {
      name: "release-control.json",
      sha256: sha256(controlContents),
    },
    identities: {
      name: "fixture-identities.json",
      sha256: sha256(input.identitiesContents),
    },
  };
  const stateContents = jsonDocument({
    version: FIXTURE_VERSION,
    profile: SYNTHETIC_RELEASE_FIXTURE_PROFILE,
    status: input.status,
    productionHumanApprovals: "NOT_EVALUATED",
    ...(isRecord(input.control)
      ? {
          releaseOrdinal: input.control.releaseOrdinal ?? null,
          cohort: input.control.cohort ?? null,
          releaseId: input.control.releaseId ?? null,
          supersedesReleaseId: input.control.supersedesReleaseId ?? null,
        }
      : {}),
    files,
  });
  publishOrReplacePrivateFile(input.boundary, "state.json", stateContents);
}

function safeGithubEnvironment(
  boundary: SyntheticReleaseFixtureBoundary,
): Readonly<Record<string, string>> {
  return {
    QA_TEMPLATE_TWIN_RUNTIME_ENV_FILE: privateFilePath(boundary, "runtime.env"),
    QA_TEMPLATE_TWIN_RELEASE_CONTROL_FILE: privateFilePath(
      boundary,
      "release-control.json",
    ),
    QA_TEMPLATE_TWIN_FIXTURE_IDENTITIES_FILE: privateFilePath(
      boundary,
      "fixture-identities.json",
    ),
    QA_TEMPLATE_TWIN_FIXTURE_STATE_FILE: privateFilePath(
      boundary,
      "state.json",
    ),
    QA_TEMPLATE_TWIN_RELEASE_PROFILE: SYNTHETIC_RELEASE_FIXTURE_PROFILE,
  };
}

function publishSafeGithubEnvironment(
  boundary: SyntheticReleaseFixtureBoundary,
): void {
  const values = safeGithubEnvironment(boundary);
  for (const [name, value] of Object.entries(values)) {
    if (
      /[\r\n]/u.test(value) ||
      (name.endsWith("_FILE") &&
        (!isAbsolute(value) || !isWithin(boundary.runnerRoot, value)))
    ) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_GITHUB_ENV_INVALID");
    }
  }
  appendFileSync(
    boundary.githubEnvironment,
    `${Object.entries(values)
      .map(([name, value]) => `${name}=${value}`)
      .join("\n")}\n`,
    { encoding: "utf8" },
  );
}

function parseRuntimeEnvironment(contents: string): Map<string, string> {
  const values = new Map<string, string>();
  for (const line of contents.trimEnd().split("\n")) {
    const separator = line.indexOf("=");
    const name = line.slice(0, separator);
    const value = line.slice(separator + 1);
    if (
      separator < 1 ||
      !/^[A-Z][A-Z0-9_]{1,100}$/u.test(name) ||
      !value ||
      /[\r\n]/u.test(value) ||
      values.has(name)
    ) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_RUNTIME_ENV_INVALID");
    }
    values.set(name, value);
  }
  return values;
}

interface ParsedRuntimeEnvelope {
  readonly keyId: string;
  readonly nonceSha256: string;
  readonly releaseIdentitySha256: string;
  readonly instanceId: string;
  readonly component: TemplateTwinRuntimeComponent;
  readonly sourceCommitSha: string;
  readonly imageDigest: string;
}

function parseRuntimeEnvelopeSummary(
  encoded: string | undefined,
): ParsedRuntimeEnvelope | undefined {
  if (!encoded || !/^[A-Za-z0-9_-]{100,8192}$/u.test(encoded)) return undefined;
  let value: unknown;
  try {
    value = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
  } catch {
    return undefined;
  }
  if (
    !isRecord(value) ||
    value.version !== "template-twin-runtime-attestation-v1" ||
    typeof value.keyId !== "string" ||
    typeof value.nonce !== "string" ||
    !UUID.test(value.nonce) ||
    typeof value.releaseIdentitySha256 !== "string" ||
    typeof value.instanceId !== "string" ||
    !["APP", "WORKER"].includes(String(value.component)) ||
    typeof value.sourceCommitSha !== "string" ||
    typeof value.imageDigest !== "string" ||
    typeof value.issuedAtEpochSeconds !== "number" ||
    !Number.isSafeInteger(value.issuedAtEpochSeconds) ||
    typeof value.expiresAtEpochSeconds !== "number" ||
    !Number.isSafeInteger(value.expiresAtEpochSeconds) ||
    value.expiresAtEpochSeconds <= value.issuedAtEpochSeconds ||
    typeof value.signature !== "string" ||
    !/^[a-f0-9]{64}$/u.test(value.signature)
  ) {
    return undefined;
  }
  return {
    keyId: value.keyId,
    nonceSha256: sha256(value.nonce),
    releaseIdentitySha256: value.releaseIdentitySha256,
    instanceId: value.instanceId,
    component: value.component as TemplateTwinRuntimeComponent,
    sourceCommitSha: value.sourceCommitSha,
    imageDigest: value.imageDigest,
  };
}

function parsePreparedDocuments(
  boundary: SyntheticReleaseFixtureBoundary,
  allowedPhases: readonly PreparedControlDocument["phase"][],
  expectedKillSwitch: "true" | "false",
  options: {
    readonly allowActiveFailClosedRuntimeTransition?: boolean;
    readonly allowPreparedActivatedRuntimeTransition?: boolean;
  } = {},
): {
  readonly state: PreparedStateDocument;
  readonly control: PreparedControlDocument;
  readonly runtimeContents: string;
  readonly identitiesContents: string;
} {
  const stateContents = readPrivateFile(boundary, "state.json");
  const controlContents = readPrivateFile(boundary, "release-control.json");
  const runtimeContents = readPrivateFile(boundary, "runtime.env");
  const identitiesContents = readPrivateFile(
    boundary,
    "fixture-identities.json",
  );
  let stateValue: unknown;
  let controlValue: unknown;
  try {
    stateValue = JSON.parse(stateContents);
    controlValue = JSON.parse(controlContents);
  } catch {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_STATE_INVALID");
  }
  if (!isRecord(stateValue) || !isRecord(controlValue)) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_STATE_INVALID");
  }
  const state = stateValue as unknown as PreparedStateDocument;
  const control = controlValue as unknown as PreparedControlDocument;
  const enabledRuntimeBeforeFailClosedTransition =
    options.allowActiveFailClosedRuntimeTransition === true &&
    control.phase === "ACTIVE" &&
    expectedKillSwitch === "true"
      ? (() => {
          const closedMarker = "QA_TEMPLATE_TWIN_KILL_SWITCH=true\n";
          const segments = runtimeContents.split(closedMarker);
          return segments.length === 2
            ? `${segments[0]}QA_TEMPLATE_TWIN_KILL_SWITCH=false\n${segments[1]}`
            : undefined;
        })()
      : undefined;
  const closedRuntimeBeforeActivation =
    options.allowPreparedActivatedRuntimeTransition === true &&
    ["PREPARED", "REPLACEMENT_PREPARED"].includes(control.phase) &&
    expectedKillSwitch === "false"
      ? (() => {
          const enabledMarker = "QA_TEMPLATE_TWIN_KILL_SWITCH=false\n";
          const segments = runtimeContents.split(enabledMarker);
          return segments.length === 2
            ? `${segments[0]}QA_TEMPLATE_TWIN_KILL_SWITCH=true\n${segments[1]}`
            : undefined;
        })()
      : undefined;
  const persistedRuntimeHashValid =
    state.files?.runtime?.sha256 === sha256(runtimeContents) ||
    (enabledRuntimeBeforeFailClosedTransition !== undefined &&
      state.files?.runtime?.sha256 ===
        sha256(enabledRuntimeBeforeFailClosedTransition)) ||
    (closedRuntimeBeforeActivation !== undefined &&
      state.files?.runtime?.sha256 === sha256(closedRuntimeBeforeActivation));
  const checkpointStatusValid =
    (["PREPARED", "REPLACEMENT_PREPARED"].includes(control.phase) &&
      control.checkpointStatus === "PENDING") ||
    (control.phase === "ACTIVE" && control.checkpointStatus === "ACTIVE") ||
    (["REVOKED", "CLEANED"].includes(control.phase) &&
      ["PENDING", "REVOKED"].includes(control.checkpointStatus));
  if (
    state.version !== FIXTURE_VERSION ||
    state.profile !== SYNTHETIC_RELEASE_FIXTURE_PROFILE ||
    !allowedPhases.includes(state.status) ||
    state.status !== control.phase ||
    state.productionHumanApprovals !== "NOT_EVALUATED" ||
    state.releaseOrdinal !== control.releaseOrdinal ||
    state.cohort !== control.cohort ||
    state.releaseId !== control.releaseId ||
    state.supersedesReleaseId !== control.supersedesReleaseId ||
    state.files?.runtime?.name !== "runtime.env" ||
    !persistedRuntimeHashValid ||
    state.files?.control?.name !== "release-control.json" ||
    state.files?.control?.sha256 !== sha256(controlContents) ||
    state.files?.identities?.name !== "fixture-identities.json" ||
    state.files?.identities?.sha256 !== sha256(identitiesContents) ||
    control.version !== FIXTURE_VERSION ||
    control.profile !== SYNTHETIC_RELEASE_FIXTURE_PROFILE ||
    !allowedPhases.includes(control.phase) ||
    control.synthetic !== true ||
    control.productionHumanApprovals !== "NOT_EVALUATED" ||
    control.approvalEvidenceLabel !== SYNTHETIC_APPROVAL_EVIDENCE_LABEL ||
    control.runId !== boundary.runId ||
    control.runAttempt !== boundary.runAttempt ||
    !Number.isSafeInteger(control.preparedAtEpochSeconds) ||
    control.preparedAtEpochSeconds < 1 ||
    !UUID.test(control.releaseId) ||
    !/^[a-f0-9]{64}$/u.test(control.releaseIdentitySha256) ||
    control.sourceCommitSha !== boundary.sourceCommitSha ||
    control.appImageDigest !== boundary.appImageDigest ||
    control.workerImageDigest !== boundary.workerImageDigest ||
    control.migratorImageDigest !== boundary.migratorImageDigest ||
    !INTEGER.test(control.releaseGeneration) ||
    !INTEGER.test(control.globalGeneration) ||
    !controlLineageIsValid(boundary, control) ||
    !/^[a-f0-9]{64}$/u.test(control.appRuntimeAttestationNonceSha256) ||
    !/^[a-f0-9]{64}$/u.test(control.workerRuntimeAttestationNonceSha256) ||
    control.appRuntimeAttestationNonceSha256 ===
      control.workerRuntimeAttestationNonceSha256 ||
    !/^[A-Za-z0-9][A-Za-z0-9._:-]{2,79}$/u.test(control.runtimeKeyId) ||
    !/^[A-Za-z0-9_-]{43}$/u.test(control.runtimeSigningSecret) ||
    control.creator?.userId !==
      SYNTHETIC_FIXTURE_IDENTITIES.administrator.creatorId ||
    !SAFE_SECRET.test(control.creator?.sessionId ?? "") ||
    control.checkpoint !== "CANARY" ||
    !checkpointStatusValid
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_STATE_INVALID");
  }

  const runtimeValues = parseRuntimeEnvironment(runtimeContents);
  const expectedRuntimeKeys = [
    "QA_TEMPLATE_TWIN_APP_IMAGE_DIGEST",
    "QA_TEMPLATE_TWIN_APP_INSTANCE_ID",
    "QA_TEMPLATE_TWIN_APP_RUNTIME_ATTESTATION",
    "QA_TEMPLATE_TWIN_KILL_SWITCH",
    "QA_TEMPLATE_TWIN_MIGRATOR_IMAGE_DIGEST",
    "QA_TEMPLATE_TWIN_RELEASE_COMMIT_SHA",
    "QA_TEMPLATE_TWIN_RELEASE_IDENTITY_SHA256",
    "QA_TEMPLATE_TWIN_RELEASE_PROFILE",
    "QA_TEMPLATE_TWIN_RUNTIME_ENV_VERSION",
    "QA_TEMPLATE_TWIN_RUNTIME_MODE",
    "QA_TEMPLATE_TWIN_WORKER_IMAGE_DIGEST",
    "QA_TEMPLATE_TWIN_WORKER_INSTANCE_ID",
    "QA_TEMPLATE_TWIN_WORKER_RUNTIME_ATTESTATION",
  ].sort();
  const appEnvelope = runtimeValues.get(
    "QA_TEMPLATE_TWIN_APP_RUNTIME_ATTESTATION",
  );
  const workerEnvelope = runtimeValues.get(
    "QA_TEMPLATE_TWIN_WORKER_RUNTIME_ATTESTATION",
  );
  const parsedAppEnvelope = parseRuntimeEnvelopeSummary(appEnvelope);
  const parsedWorkerEnvelope = parseRuntimeEnvelopeSummary(workerEnvelope);
  if (
    [...runtimeValues.keys()].sort().join("\n") !==
      expectedRuntimeKeys.join("\n") ||
    runtimeValues.get("QA_TEMPLATE_TWIN_RUNTIME_ENV_VERSION") !==
      RUNTIME_ENV_VERSION ||
    runtimeValues.get("QA_TEMPLATE_TWIN_RELEASE_PROFILE") !==
      SYNTHETIC_RELEASE_FIXTURE_PROFILE ||
    runtimeValues.get("QA_TEMPLATE_TWIN_KILL_SWITCH") !== expectedKillSwitch ||
    runtimeValues.get("QA_TEMPLATE_TWIN_RUNTIME_MODE") !== "standard" ||
    runtimeValues.get("QA_TEMPLATE_TWIN_RELEASE_IDENTITY_SHA256") !==
      control.releaseIdentitySha256 ||
    runtimeValues.get("QA_TEMPLATE_TWIN_RELEASE_COMMIT_SHA") !==
      boundary.sourceCommitSha ||
    runtimeValues.get("QA_TEMPLATE_TWIN_APP_IMAGE_DIGEST") !==
      boundary.appImageDigest ||
    runtimeValues.get("QA_TEMPLATE_TWIN_WORKER_IMAGE_DIGEST") !==
      boundary.workerImageDigest ||
    runtimeValues.get("QA_TEMPLATE_TWIN_MIGRATOR_IMAGE_DIGEST") !==
      boundary.migratorImageDigest ||
    runtimeValues.get("QA_TEMPLATE_TWIN_APP_INSTANCE_ID") !==
      control.appInstanceId ||
    runtimeValues.get("QA_TEMPLATE_TWIN_WORKER_INSTANCE_ID") !==
      control.workerInstanceId ||
    !appEnvelope ||
    !workerEnvelope ||
    appEnvelope === workerEnvelope ||
    !parsedAppEnvelope ||
    parsedAppEnvelope.keyId !== control.runtimeKeyId ||
    parsedAppEnvelope.nonceSha256 !==
      control.appRuntimeAttestationNonceSha256 ||
    parsedAppEnvelope.releaseIdentitySha256 !== control.releaseIdentitySha256 ||
    parsedAppEnvelope.instanceId !== control.appInstanceId ||
    parsedAppEnvelope.component !== "APP" ||
    parsedAppEnvelope.sourceCommitSha !== control.sourceCommitSha ||
    parsedAppEnvelope.imageDigest !== control.appImageDigest ||
    !parsedWorkerEnvelope ||
    parsedWorkerEnvelope.keyId !== control.runtimeKeyId ||
    parsedWorkerEnvelope.nonceSha256 !==
      control.workerRuntimeAttestationNonceSha256 ||
    parsedWorkerEnvelope.releaseIdentitySha256 !==
      control.releaseIdentitySha256 ||
    parsedWorkerEnvelope.instanceId !== control.workerInstanceId ||
    parsedWorkerEnvelope.component !== "WORKER" ||
    parsedWorkerEnvelope.sourceCommitSha !== control.sourceCommitSha ||
    parsedWorkerEnvelope.imageDigest !== control.workerImageDigest
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_STATE_INVALID");
  }
  return { state, control, runtimeContents, identitiesContents };
}

async function prepareFixture(
  boundary: SyntheticReleaseFixtureBoundary,
): Promise<void> {
  process.env.NODE_ENV = "test";
  process.env.TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL =
    boundary.releaseControlDatabaseUrl;
  process.env.TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL =
    boundary.releaseControlDatabaseUrl;

  const owner = client(boundary.ownerDatabaseUrl);
  const runtimePrincipalProbe = client(boundary.runtimeDatabaseUrl);
  let releaseControlDatabase: PrismaClient | undefined;
  try {
    const [releaseControl, releaseControlDb] = await Promise.all([
      import("../../../apps/transcribe-md/src/lib/template-twin/release-control"),
      import("../../../apps/transcribe-md/src/lib/template-twin/release-control-db"),
    ]);
    releaseControlDatabase = releaseControlDb.default as PrismaClient;
    await Promise.all([
      assertDatabaseIdentity(owner, "meddoc"),
      assertDatabaseIdentity(releaseControlDatabase, "meddoc_release_control"),
      assertDatabaseIdentity(runtimePrincipalProbe, "meddoc_runtime"),
    ]);

    const evidence = syntheticEvidence(boundary);
    const releaseOrdinal = 1;
    const cohort = "INFRASTRUCTURE" as const;
    const authorizedPracticeIds = cohortPracticeIds(cohort);
    const { appInstanceId, workerInstanceId } = runtimeIdentity(
      boundary,
      releaseOrdinal,
    );
    mkdirSync(boundary.outputDirectory, { mode: 0o700 });
    chmodSync(boundary.outputDirectory, 0o700);

    const authority = await seedFixtureAuthority({ owner, boundary });
    const identitiesContents = jsonDocument({
      version: FIXTURE_VERSION,
      profile: SYNTHETIC_RELEASE_FIXTURE_PROFILE,
      synthetic: true,
      phi: "FORBIDDEN",
      productionUse: "FORBIDDEN",
      identities: {
        infrastructure: {
          ...SYNTHETIC_FIXTURE_IDENTITIES.infrastructure,
          password: authority.doctorPasswords.infrastructure,
        },
        stagingPrimary: {
          ...SYNTHETIC_FIXTURE_IDENTITIES.stagingPrimary,
          password: authority.doctorPasswords.stagingPrimary,
        },
        stagingForeign: {
          ...SYNTHETIC_FIXTURE_IDENTITIES.stagingForeign,
          password: authority.doctorPasswords.stagingForeign,
        },
      },
    });
    const globalRows = await owner.$queryRaw<Array<{ generation: bigint }>>(
      Prisma.sql`
        SELECT "generation" FROM "template_twin_rollout_controls"
        WHERE "id" = 'global'
      `,
    );
    const globalGeneration = globalRows[0]?.generation;
    if (globalGeneration === undefined) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_CONTROL_INVALID");
    }
    const lifecycleControl = {
      version: FIXTURE_VERSION,
      profile: SYNTHETIC_RELEASE_FIXTURE_PROFILE,
      phase: "SEEDED",
      synthetic: true,
      productionHumanApprovals: "NOT_EVALUATED",
      approvalEvidenceLabel: SYNTHETIC_APPROVAL_EVIDENCE_LABEL,
      runId: boundary.runId,
      runAttempt: boundary.runAttempt,
      sourceCommitSha: evidence.sourceCommitSha,
      appImageDigest: evidence.appImageDigest,
      workerImageDigest: evidence.workerImageDigest,
      migratorImageDigest: evidence.migratorImageDigest,
      globalGeneration: globalGeneration.toString(),
      releaseOrdinal,
      cohort,
      authorizedPracticeIds,
      supersedesReleaseId: null,
      supersededReleases: [],
      appInstanceId,
      workerInstanceId,
      runtimeKeyId: authority.runtimeKeyId,
      runtimeSigningSecret: Buffer.from(
        authority.runtimeSigningSecret,
      ).toString("base64url"),
      creator: authority.creator,
      checkpoint: "CANARY",
      checkpointStatus: "PENDING",
    } as const;
    persistLifecycleCheckpoint({
      boundary,
      status: "SEEDED",
      control: lifecycleControl,
      identitiesContents,
    });

    const created = await releaseControl.createTemplateTwinReleaseCandidate({
      actor: authority.creator,
      confirmation: "CREATE EXACT RELEASE",
      evidence,
      guardrailPolicy: syntheticGuardrailPolicy(),
      authorizedPracticeIds,
      canaryPracticeIds: authorizedPracticeIds,
      runtimeInstances: [
        {
          instanceId: appInstanceId,
          component: "APP",
          imageDigest: evidence.appImageDigest,
        },
        {
          instanceId: workerInstanceId,
          component: "WORKER",
          imageDigest: evidence.workerImageDigest,
        },
      ],
    });
    let releaseGeneration = created.generation;
    const createdControl = {
      ...lifecycleControl,
      phase: "CREATED",
      releaseId: created.releaseId,
      releaseIdentitySha256: created.releaseIdentitySha256,
      releaseGeneration,
    } as const;
    persistLifecycleCheckpoint({
      boundary,
      status: "CREATED",
      control: createdControl,
      identitiesContents,
    });

    releaseGeneration = (
      await releaseControl.freezeTemplateTwinReleaseCandidate({
        actor: authority.creator,
        releaseId: created.releaseId,
        expectedReleaseGeneration: releaseGeneration,
        confirmation: `FREEZE ${created.releaseIdentitySha256.slice(0, 12)}`,
      })
    ).generation;
    persistLifecycleCheckpoint({
      boundary,
      status: "FROZEN",
      control: {
        ...createdControl,
        phase: "FROZEN",
        releaseGeneration,
      },
      identitiesContents,
    });

    const approvalEvidenceSha256 = sha256(SYNTHETIC_APPROVAL_EVIDENCE_LABEL);
    for (const discipline of TEMPLATE_TWIN_RELEASE_DISCIPLINES) {
      const approval = await releaseControl.recordTemplateTwinReleaseApproval({
        actor: authority.reviewers.get(discipline)!,
        releaseId: created.releaseId,
        expectedReleaseGeneration: releaseGeneration,
        discipline,
        decision: "APPROVE",
        evidenceSha256: approvalEvidenceSha256,
        confirmation: templateTwinApprovalConfirmation({
          decision: "APPROVE",
          discipline,
          releaseIdentitySha256: created.releaseIdentitySha256,
        }),
      });
      releaseGeneration = approval.generation;
      persistLifecycleCheckpoint({
        boundary,
        status: `APPROVAL_${discipline}`,
        control: {
          ...createdControl,
          phase: `APPROVAL_${discipline}`,
          releaseGeneration,
        },
        identitiesContents,
      });
    }

    const issuedAtEpochSeconds = Math.floor(Date.now() / 1_000) - 1;
    const expiresAtEpochSeconds = issuedAtEpochSeconds + 4 * 60 * 60;
    const commonEnvelope = {
      keyId: authority.runtimeKeyId,
      signingSecret: authority.runtimeSigningSecret,
      releaseIdentitySha256: created.releaseIdentitySha256,
      sourceCommitSha: evidence.sourceCommitSha,
      appImageDigest: evidence.appImageDigest,
      workerImageDigest: evidence.workerImageDigest,
      issuedAtEpochSeconds,
      expiresAtEpochSeconds,
    } as const;
    const appRuntimeAttestationNonce = randomUUID();
    const workerRuntimeAttestationNonce = randomUUID();
    const appRuntimeAttestation = buildSyntheticRuntimeEnvelope({
      ...commonEnvelope,
      instanceId: appInstanceId,
      component: "APP",
      nonce: appRuntimeAttestationNonce,
    });
    const workerRuntimeAttestation = buildSyntheticRuntimeEnvelope({
      ...commonEnvelope,
      instanceId: workerInstanceId,
      component: "WORKER",
      nonce: workerRuntimeAttestationNonce,
    });
    assert.notEqual(appRuntimeAttestation, workerRuntimeAttestation);
    const runtimeContents = serializeSyntheticRuntimeEnvironment({
      killSwitch: "true",
      releaseIdentitySha256: created.releaseIdentitySha256,
      sourceCommitSha: evidence.sourceCommitSha,
      appImageDigest: evidence.appImageDigest,
      workerImageDigest: evidence.workerImageDigest,
      migratorImageDigest: evidence.migratorImageDigest,
      appInstanceId,
      workerInstanceId,
      appRuntimeAttestation,
      workerRuntimeAttestation,
    });
    const preparedAtEpochSeconds = Math.floor(Date.now() / 1_000);
    const control: PreparedControlDocument = {
      version: FIXTURE_VERSION,
      profile: SYNTHETIC_RELEASE_FIXTURE_PROFILE,
      phase: "PREPARED",
      synthetic: true,
      productionHumanApprovals: "NOT_EVALUATED",
      approvalEvidenceLabel: SYNTHETIC_APPROVAL_EVIDENCE_LABEL,
      runId: boundary.runId,
      runAttempt: boundary.runAttempt,
      preparedAtEpochSeconds,
      releaseOrdinal,
      cohort,
      authorizedPracticeIds,
      supersedesReleaseId: null,
      supersededReleases: [],
      releaseId: created.releaseId,
      releaseIdentitySha256: created.releaseIdentitySha256,
      sourceCommitSha: evidence.sourceCommitSha,
      appImageDigest: evidence.appImageDigest,
      workerImageDigest: evidence.workerImageDigest,
      migratorImageDigest: evidence.migratorImageDigest,
      releaseGeneration,
      globalGeneration: globalGeneration.toString(),
      appInstanceId,
      workerInstanceId,
      appRuntimeAttestationNonceSha256: sha256(appRuntimeAttestationNonce),
      workerRuntimeAttestationNonceSha256: sha256(
        workerRuntimeAttestationNonce,
      ),
      runtimeKeyId: authority.runtimeKeyId,
      runtimeSigningSecret: Buffer.from(
        authority.runtimeSigningSecret,
      ).toString("base64url"),
      creator: authority.creator,
      checkpoint: "CANARY",
      checkpointStatus: "PENDING",
    };
    const readinessRows = await owner.$queryRaw<Array<{ ready: boolean }>>(
      Prisma.sql`
        SELECT template_twin_release_runtime_ready(
          ${created.releaseId}::UUID,
          ${created.releaseIdentitySha256}::CHAR(64)
        ) AS "ready"
      `,
    );
    if (readinessRows[0]?.ready !== false) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_PREMATURE_READINESS");
    }
    persistLifecycleCheckpoint({
      boundary,
      status: "PREPARED",
      control,
      identitiesContents,
      runtimeContents,
    });
    publishSafeGithubEnvironment(boundary);
  } finally {
    await Promise.all([
      owner.$disconnect(),
      runtimePrincipalProbe.$disconnect(),
      releaseControlDatabase?.$disconnect(),
    ]);
  }
}

async function readReleaseControlState(
  owner: PrismaClient,
  releaseId: string,
): Promise<ReleaseControlStateRow> {
  const rows = await owner.$queryRaw<ReleaseControlStateRow[]>(Prisma.sql`
    SELECT control."enabled", control."generation" AS "globalGeneration",
      candidate."status" AS "releaseStatus",
      candidate."generation" AS "releaseGeneration",
      checkpoint."status" AS "checkpointStatus"
    FROM "template_twin_rollout_controls" control
    JOIN "template_twin_release_candidates" candidate
      ON candidate."id" = ${releaseId}::UUID
    JOIN "template_twin_release_checkpoints" checkpoint
      ON checkpoint."releaseId" = candidate."id"
     AND checkpoint."stage" = 'CANARY'
    WHERE control."id" = 'global'
  `);
  if (rows.length !== 1) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_CONTROL_INVALID");
  }
  return rows[0]!;
}

async function assertFreshRuntimeReceipts(input: {
  readonly owner: PrismaClient;
  readonly control: PreparedControlDocument;
}): Promise<void> {
  const rows = await input.owner.$queryRaw<RuntimeReceiptRow[]>(Prisma.sql`
    SELECT requirement."component"::TEXT AS "component",
      requirement."instanceId", requirement."imageDigest",
      EXISTS (
        SELECT 1
        FROM "template_twin_release_runtime_attestations" attestation
        JOIN "template_twin_release_attestation_keys" key
          ON key."keyId" = attestation."keyId"
         AND key."purpose" = 'RUNTIME'
         AND key."effectiveAt" <= CURRENT_TIMESTAMP
         AND key."expiresAt" > CURRENT_TIMESTAMP
         AND key."revokedAt" IS NULL
        WHERE attestation."releaseId" = requirement."releaseId"
          AND attestation."requirementId" = requirement."id"
          AND attestation."releaseIdentitySha256" =
            requirement."releaseIdentitySha256"
          AND attestation."instanceId" = requirement."instanceId"
          AND attestation."component" = requirement."component"
          AND attestation."sourceCommitSha" = requirement."sourceCommitSha"
          AND attestation."imageDigest" = requirement."imageDigest"
          AND attestation."keyId" = ${input.control.runtimeKeyId}
          AND attestation."nonceSha256" = CASE requirement."component"
            WHEN 'APP' THEN
              ${input.control.appRuntimeAttestationNonceSha256}::CHAR(64)
            WHEN 'WORKER' THEN
              ${input.control.workerRuntimeAttestationNonceSha256}::CHAR(64)
            ELSE NULL
          END
          AND attestation."expiresAt" >
            CURRENT_TIMESTAMP + INTERVAL '30 seconds'
          AND attestation."lastSeenAt" >
            CURRENT_TIMESTAMP - INTERVAL '75 seconds'
          AND attestation."lastSeenAt" >=
            to_timestamp(${input.control.preparedAtEpochSeconds})
      ) AS "ready"
    FROM "template_twin_release_runtime_requirements" requirement
    WHERE requirement."releaseId" = ${input.control.releaseId}::UUID
      AND requirement."releaseIdentitySha256" =
        ${input.control.releaseIdentitySha256}::CHAR(64)
    ORDER BY requirement."component", requirement."instanceId"
  `);
  const expected = [
    {
      component: "APP",
      instanceId: input.control.appInstanceId,
      imageDigest: input.control.appImageDigest,
    },
    {
      component: "WORKER",
      instanceId: input.control.workerInstanceId,
      imageDigest: input.control.workerImageDigest,
    },
  ];
  if (
    rows.length !== expected.length ||
    rows.some((row, index) => {
      const required = expected[index];
      return (
        !required ||
        row.component !== required.component ||
        row.instanceId !== required.instanceId ||
        row.imageDigest !== required.imageDigest ||
        row.ready !== true
      );
    })
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_RUNTIME_NOT_READY");
  }
}

async function activateFixture(
  boundary: SyntheticReleaseFixtureBoundary,
): Promise<void> {
  process.env.NODE_ENV = "test";
  process.env.TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL =
    boundary.releaseControlDatabaseUrl;
  process.env.TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL =
    boundary.releaseControlDatabaseUrl;

  const runtimeKillSwitch = readPersistedRuntimeKillSwitch(boundary);
  const prepared = parsePreparedDocuments(
    boundary,
    ["PREPARED", "REPLACEMENT_PREPARED"],
    runtimeKillSwitch,
    {
      // The release-control transaction commits before ACTIVE evidence is
      // published. A retry may therefore observe the exact prior PREPARED
      // state hash with its otherwise identical runtime document already
      // opened; the DB generation branch below proves whether activation won.
      allowPreparedActivatedRuntimeTransition: runtimeKillSwitch === "false",
    },
  );
  const runtimeValues = parseRuntimeEnvironment(prepared.runtimeContents);
  const owner = client(boundary.ownerDatabaseUrl);
  const runtimePrincipalProbe = client(boundary.runtimeDatabaseUrl);
  let releaseControlDatabase: PrismaClient | undefined;
  try {
    const [releaseControl, releaseControlDb] = await Promise.all([
      import("../../../apps/transcribe-md/src/lib/template-twin/release-control"),
      import("../../../apps/transcribe-md/src/lib/template-twin/release-control-db"),
    ]);
    releaseControlDatabase = releaseControlDb.default as PrismaClient;
    await Promise.all([
      assertDatabaseIdentity(owner, "meddoc"),
      assertDatabaseIdentity(releaseControlDatabase, "meddoc_release_control"),
      assertDatabaseIdentity(runtimePrincipalProbe, "meddoc_runtime"),
    ]);

    const before = await readReleaseControlState(
      owner,
      prepared.control.releaseId,
    );
    let releaseGeneration: string;
    let globalGeneration: string;
    if (
      before.enabled === false &&
      before.releaseStatus === "APPROVED" &&
      before.checkpointStatus === "PENDING" &&
      before.releaseGeneration.toString() ===
        prepared.control.releaseGeneration &&
      before.globalGeneration.toString() === prepared.control.globalGeneration
    ) {
      if (runtimeKillSwitch !== "true") {
        fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_CONTROL_INVALID");
      }
      // The fixture never submits an attestation. These exact fresh rows can
      // therefore exist only after the real app and worker have started with
      // the protected PREPARED environment and refreshed their own receipts.
      await assertFreshRuntimeReceipts({
        owner,
        control: prepared.control,
      });
      const activation =
        await releaseControl.activateTemplateTwinReleaseCheckpoint({
          actor: prepared.control.creator,
          releaseId: prepared.control.releaseId,
          stage: "CANARY",
          expectedReleaseGeneration: prepared.control.releaseGeneration,
          expectedGlobalGeneration: prepared.control.globalGeneration,
          confirmation: templateTwinCheckpointConfirmation({
            verb: "ACTIVATE",
            stage: "CANARY",
            releaseIdentitySha256: prepared.control.releaseIdentitySha256,
          }),
          env: {
            TEMPLATE_TWIN_KILL_SWITCH: "false",
            TEMPLATE_TWIN_RUNTIME_MODE: "standard",
            TEMPLATE_TWIN_RELEASE_COMMIT_SHA: prepared.control.sourceCommitSha,
            TEMPLATE_TWIN_APP_IMAGE_DIGEST: prepared.control.appImageDigest,
            TEMPLATE_TWIN_WORKER_IMAGE_DIGEST:
              prepared.control.workerImageDigest,
            TEMPLATE_TWIN_MIGRATOR_IMAGE_DIGEST:
              prepared.control.migratorImageDigest,
          },
        });
      releaseGeneration = activation.releaseGeneration;
      globalGeneration = activation.globalGeneration;
    } else if (
      before.enabled === true &&
      before.releaseStatus === "ROLLING_OUT" &&
      before.checkpointStatus === "ACTIVE" &&
      before.releaseGeneration ===
        BigInt(prepared.control.releaseGeneration) + BigInt(1) &&
      before.globalGeneration ===
        BigInt(prepared.control.globalGeneration) + BigInt(1)
    ) {
      // Recovery after the release-control transaction committed but before
      // the protected ACTIVE files were atomically published.
      releaseGeneration = before.releaseGeneration.toString();
      globalGeneration = before.globalGeneration.toString();
    } else {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_CONTROL_INVALID");
    }

    const after = await readReleaseControlState(
      owner,
      prepared.control.releaseId,
    );
    if (
      !after.enabled ||
      after.releaseStatus !== "ROLLING_OUT" ||
      after.checkpointStatus !== "ACTIVE"
    ) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_CONTROL_INVALID");
    }
    await assertSyntheticPracticeExposure(
      owner,
      prepared.control.authorizedPracticeIds,
    );

    const runtimeContents = serializeSyntheticRuntimeEnvironment({
      killSwitch: "false",
      releaseIdentitySha256: prepared.control.releaseIdentitySha256,
      sourceCommitSha: prepared.control.sourceCommitSha,
      appImageDigest: prepared.control.appImageDigest,
      workerImageDigest: prepared.control.workerImageDigest,
      migratorImageDigest: prepared.control.migratorImageDigest,
      appInstanceId: prepared.control.appInstanceId,
      workerInstanceId: prepared.control.workerInstanceId,
      appRuntimeAttestation: runtimeValues.get(
        "QA_TEMPLATE_TWIN_APP_RUNTIME_ATTESTATION",
      )!,
      workerRuntimeAttestation: runtimeValues.get(
        "QA_TEMPLATE_TWIN_WORKER_RUNTIME_ATTESTATION",
      )!,
    });
    const control: PreparedControlDocument = {
      ...prepared.control,
      phase: "ACTIVE",
      releaseGeneration,
      globalGeneration,
      checkpointStatus: "ACTIVE",
    };
    persistLifecycleCheckpoint({
      boundary,
      status: "ACTIVE",
      control,
      identitiesContents: prepared.identitiesContents,
      runtimeContents,
    });
  } finally {
    await Promise.all([
      owner.$disconnect(),
      runtimePrincipalProbe.$disconnect(),
      releaseControlDatabase?.$disconnect(),
    ]);
  }
}

function readFinalLifecyclePhase(
  boundary: SyntheticReleaseFixtureBoundary,
): PreparedControlDocument["phase"] {
  let control: unknown;
  let state: unknown;
  try {
    control = JSON.parse(readPrivateFile(boundary, "release-control.json"));
    state = JSON.parse(readPrivateFile(boundary, "state.json"));
  } catch {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_STATE_INVALID");
  }
  const phases: readonly PreparedControlDocument["phase"][] = [
    "PREPARED",
    "ACTIVE",
    "REPLACEMENT_PREPARED",
    "REVOKED",
    "CLEANED",
  ];
  if (
    !isRecord(control) ||
    !isRecord(state) ||
    typeof control.phase !== "string" ||
    !phases.includes(control.phase as PreparedControlDocument["phase"]) ||
    state.status !== control.phase
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_STATE_INVALID");
  }
  return control.phase as PreparedControlDocument["phase"];
}

function readPersistedRuntimeKillSwitch(
  boundary: SyntheticReleaseFixtureBoundary,
): "true" | "false" {
  const value = parseRuntimeEnvironment(
    readPrivateFile(boundary, "runtime.env"),
  ).get("QA_TEMPLATE_TWIN_KILL_SWITCH");
  if (value !== "true" && value !== "false") {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_STATE_INVALID");
  }
  return value;
}

function parseFinalLifecycleDocuments(
  boundary: SyntheticReleaseFixtureBoundary,
  allowedPhases: readonly PreparedControlDocument["phase"][],
): ReturnType<typeof parsePreparedDocuments> {
  const phase = readFinalLifecyclePhase(boundary);
  if (!allowedPhases.includes(phase)) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_STATE_INVALID");
  }
  const runtimeKillSwitch = readPersistedRuntimeKillSwitch(boundary);
  if (
    !["ACTIVE", "PREPARED", "REPLACEMENT_PREPARED"].includes(phase) &&
    runtimeKillSwitch !== "true"
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_STATE_INVALID");
  }
  return parsePreparedDocuments(boundary, allowedPhases, runtimeKillSwitch, {
    // Revocation writes the process-level kill switch before it mutates
    // persisted rollout authority. A process death between those writes
    // leaves the last committed ACTIVE state hash alongside the exact closed
    // runtime document; admit only that one-way fail-closed recovery shape.
    allowActiveFailClosedRuntimeTransition:
      phase === "ACTIVE" && runtimeKillSwitch === "true",
    allowPreparedActivatedRuntimeTransition:
      ["PREPARED", "REPLACEMENT_PREPARED"].includes(phase) &&
      runtimeKillSwitch === "false",
  });
}

function runtimeEnvironmentForControl(input: {
  readonly control: PreparedControlDocument;
  readonly runtimeContents: string;
  readonly killSwitch: "true" | "false";
}): string {
  const values = parseRuntimeEnvironment(input.runtimeContents);
  return serializeSyntheticRuntimeEnvironment({
    killSwitch: input.killSwitch,
    releaseIdentitySha256: input.control.releaseIdentitySha256,
    sourceCommitSha: input.control.sourceCommitSha,
    appImageDigest: input.control.appImageDigest,
    workerImageDigest: input.control.workerImageDigest,
    migratorImageDigest: input.control.migratorImageDigest,
    appInstanceId: input.control.appInstanceId,
    workerInstanceId: input.control.workerInstanceId,
    appRuntimeAttestation: values.get(
      "QA_TEMPLATE_TWIN_APP_RUNTIME_ATTESTATION",
    )!,
    workerRuntimeAttestation: values.get(
      "QA_TEMPLATE_TWIN_WORKER_RUNTIME_ATTESTATION",
    )!,
  });
}

async function assertSyntheticPracticeExposure(
  owner: PrismaClient,
  enabledPracticeIds: readonly string[],
): Promise<void> {
  const rows = await owner.$queryRaw<Array<{ id: string; enabled: boolean }>>(
    Prisma.sql`
      SELECT "id", "templateTwinEnabled" AS "enabled"
      FROM "practices"
      WHERE "id" IN (${Prisma.join(allFixturePracticeIds)})
      ORDER BY "id"
    `,
  );
  if (
    rows.length !== allFixturePracticeIds.length ||
    rows.some(({ id, enabled }) => enabled !== enabledPracticeIds.includes(id))
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_CONTROL_INVALID");
  }
}

async function loadSyntheticReviewerActors(
  owner: PrismaClient,
): Promise<
  ReadonlyMap<TemplateTwinReleaseDiscipline, TemplateTwinReleaseActor>
> {
  const reviewerIds = new Map<TemplateTwinReleaseDiscipline, string>(
    TEMPLATE_TWIN_RELEASE_DISCIPLINES.map((discipline) => [
      discipline,
      `synthetic_ci_template_twin_reviewer_${discipline.toLowerCase()}`,
    ]),
  );
  const rows = await owner.$queryRaw<
    Array<{ userId: string; sessionToken: string }>
  >(Prisma.sql`
    SELECT DISTINCT ON (session."userId")
      session."userId", session."sessionToken"
    FROM "user_sessions" session
    WHERE session."userId" IN (${Prisma.join([...reviewerIds.values()])})
      AND session."createdAt" <= CURRENT_TIMESTAMP
      AND session."createdAt" > CURRENT_TIMESTAMP - INTERVAL '12 hours'
      AND session."expiresAt" > CURRENT_TIMESTAMP
    ORDER BY session."userId", session."createdAt" DESC
  `);
  const sessions = new Map(rows.map((row) => [row.userId, row.sessionToken]));
  if (
    rows.length !== TEMPLATE_TWIN_RELEASE_DISCIPLINES.length ||
    [...sessions.values()].some((session) => !SAFE_SECRET.test(session))
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_AUTHORITY_INVALID");
  }
  return new Map(
    TEMPLATE_TWIN_RELEASE_DISCIPLINES.map((discipline) => {
      const userId = reviewerIds.get(discipline)!;
      const sessionId = sessions.get(userId);
      if (!sessionId) {
        fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_AUTHORITY_INVALID");
      }
      return [discipline, { userId, sessionId }];
    }),
  );
}

async function prepareReplacementFixture(
  boundary: SyntheticReleaseFixtureBoundary,
): Promise<void> {
  const lifecyclePhase = readFinalLifecyclePhase(boundary);
  if (
    lifecyclePhase !== "ACTIVE" &&
    lifecyclePhase !== "REPLACEMENT_PREPARED"
  ) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_STATE_INVALID");
  }
  const alreadyPrepared = lifecyclePhase === "REPLACEMENT_PREPARED";
  const runtimeKillSwitch =
    lifecyclePhase === "ACTIVE"
      ? readPersistedRuntimeKillSwitch(boundary)
      : "true";
  const active = parsePreparedDocuments(
    boundary,
    [lifecyclePhase],
    runtimeKillSwitch,
    {
      allowActiveFailClosedRuntimeTransition:
        lifecyclePhase === "ACTIVE" && runtimeKillSwitch === "true",
    },
  );
  if (!alreadyPrepared && active.control.releaseOrdinal >= 99) {
    fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_ORDINAL_INVALID");
  }
  const disabledRuntimeContents = runtimeEnvironmentForControl({
    control: active.control,
    runtimeContents: active.runtimeContents,
    killSwitch: "true",
  });
  // Fail closed before revoking the old immutable release. The workflow must
  // recreate both runtimes before any replacement receipt can be admitted.
  if (!alreadyPrepared) {
    replacePrivateFileAtomically(
      boundary,
      "runtime.env",
      disabledRuntimeContents,
    );
  }
  const owner = client(boundary.ownerDatabaseUrl);
  const runtimePrincipalProbe = client(boundary.runtimeDatabaseUrl);
  process.env.NODE_ENV = "test";
  process.env.TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL =
    boundary.releaseControlDatabaseUrl;
  process.env.TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL =
    boundary.releaseControlDatabaseUrl;
  let releaseControlDatabase: PrismaClient | undefined;
  try {
    const [releaseControl, releaseControlDb] = await Promise.all([
      import("../../../apps/transcribe-md/src/lib/template-twin/release-control"),
      import("../../../apps/transcribe-md/src/lib/template-twin/release-control-db"),
    ]);
    releaseControlDatabase = releaseControlDb.default as PrismaClient;
    await Promise.all([
      assertDatabaseIdentity(owner, "meddoc"),
      assertDatabaseIdentity(releaseControlDatabase, "meddoc_release_control"),
      assertDatabaseIdentity(runtimePrincipalProbe, "meddoc_runtime"),
    ]);
    const before = await readReleaseControlState(
      owner,
      active.control.releaseId,
    );
    const oldSigningSecret = Buffer.from(
      active.control.runtimeSigningSecret,
      "base64url",
    );
    const keyRows = await owner.$queryRaw<
      Array<{
        secretMatches: boolean;
        currentlyValid: boolean;
        revoked: boolean;
      }>
    >(
      Prisma.sql`
        SELECT "secret" = ${oldSigningSecret} AS "secretMatches",
          "effectiveAt" <= CURRENT_TIMESTAMP
            AND "expiresAt" > CURRENT_TIMESTAMP
            AND "revokedAt" IS NULL AS "currentlyValid",
          "revokedAt" IS NOT NULL AS "revoked"
        FROM "template_twin_release_attestation_keys"
        WHERE "keyId" = ${active.control.runtimeKeyId}
          AND "purpose" = 'RUNTIME'
      `,
    );
    const key = keyRows[0];
    if (
      oldSigningSecret.length !== 32 ||
      keyRows.length !== 1 ||
      key?.secretMatches !== true
    ) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_RUNTIME_KEY_INVALID");
    }
    if (alreadyPrepared) {
      if (
        key.currentlyValid !== true ||
        key.revoked !== false ||
        before.enabled ||
        before.releaseStatus !== "APPROVED" ||
        before.checkpointStatus !== "PENDING" ||
        before.releaseGeneration.toString() !==
          active.control.releaseGeneration ||
        before.globalGeneration.toString() !== active.control.globalGeneration
      ) {
        fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_CONTROL_INVALID");
      }
      await assertSyntheticPracticeExposure(owner, []);
      publishSafeGithubEnvironment(boundary);
      return;
    }
    const releaseWasActive =
      before.enabled &&
      before.releaseStatus === "ROLLING_OUT" &&
      before.checkpointStatus === "ACTIVE" &&
      before.releaseGeneration.toString() ===
        active.control.releaseGeneration &&
      before.globalGeneration.toString() === active.control.globalGeneration;
    const releaseWasAlreadyRevoked =
      !before.enabled &&
      before.releaseStatus === "REVOKED" &&
      ["PENDING", "REVOKED"].includes(before.checkpointStatus) &&
      before.releaseGeneration ===
        BigInt(active.control.releaseGeneration) + BigInt(1) &&
      before.globalGeneration ===
        BigInt(active.control.globalGeneration) + BigInt(1);
    if (
      (!releaseWasActive && !releaseWasAlreadyRevoked) ||
      (releaseWasActive &&
        (key.currentlyValid !== true || key.revoked !== false))
    ) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_CONTROL_INVALID");
    }
    let revoked = before;
    if (releaseWasActive) {
      await assertSyntheticPracticeExposure(
        owner,
        active.control.authorizedPracticeIds,
      );
      await releaseControl.revokeTemplateTwinRelease({
        actor: active.control.creator,
        releaseId: active.control.releaseId,
        expectedReleaseGeneration: before.releaseGeneration.toString(),
        expectedGlobalGeneration: before.globalGeneration.toString(),
        reasonCode: "SYNTHETIC_CI_FIXTURE_SUPERSEDED",
        confirmation: `REVOKE ${active.control.releaseIdentitySha256.slice(0, 12)}`,
      });
      revoked = await readReleaseControlState(owner, active.control.releaseId);
    }
    await assertSyntheticPracticeExposure(owner, []);
    if (
      revoked.enabled ||
      revoked.releaseStatus !== "REVOKED" ||
      !["PENDING", "REVOKED"].includes(revoked.checkpointStatus)
    ) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_CONTROL_INVALID");
    }
    await owner.$executeRaw(Prisma.sql`
      UPDATE "template_twin_release_attestation_keys"
      SET "revokedAt" = CURRENT_TIMESTAMP
      WHERE "keyId" = ${active.control.runtimeKeyId}
        AND "purpose" = 'RUNTIME' AND "revokedAt" IS NULL
    `);
    const oldKeyRows = await owner.$queryRaw<Array<{ revoked: boolean }>>(
      Prisma.sql`
        SELECT "revokedAt" IS NOT NULL AS "revoked"
        FROM "template_twin_release_attestation_keys"
        WHERE "keyId" = ${active.control.runtimeKeyId}
          AND "purpose" = 'RUNTIME'
      `,
    );
    if (oldKeyRows.length !== 1 || oldKeyRows[0]?.revoked !== true) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_RUNTIME_KEY_INVALID");
    }
    const supersededRelease: SupersededReleaseDocument = {
      releaseOrdinal: active.control.releaseOrdinal,
      cohort: active.control.cohort,
      releaseId: active.control.releaseId,
      releaseIdentitySha256: active.control.releaseIdentitySha256,
      releaseGeneration: revoked.releaseGeneration.toString(),
      globalGeneration: revoked.globalGeneration.toString(),
      appInstanceId: active.control.appInstanceId,
      workerInstanceId: active.control.workerInstanceId,
      runtimeKeyId: active.control.runtimeKeyId,
      status: "REVOKED",
    };
    const supersededReleases = [
      ...active.control.supersededReleases,
      supersededRelease,
    ];
    persistLifecycleCheckpoint({
      boundary,
      status: "REPLACEMENT_REVOKED",
      control: {
        ...active.control,
        phase: "REPLACEMENT_REVOKED",
        supersedesReleaseId: active.control.releaseId,
        supersededReleases,
        releaseGeneration: revoked.releaseGeneration.toString(),
        globalGeneration: revoked.globalGeneration.toString(),
        checkpointStatus: revoked.checkpointStatus,
      },
      identitiesContents: active.identitiesContents,
      runtimeContents: disabledRuntimeContents,
    });

    const releaseOrdinal = active.control.releaseOrdinal + 1;
    const cohort = "STAGING" as const;
    const authorizedPracticeIds = cohortPracticeIds(cohort);
    const replacementRuntime = runtimeIdentity(boundary, releaseOrdinal);
    const signingSecret = randomBytes(32);
    const now = Date.now();
    await owner.$executeRaw(Prisma.sql`
      INSERT INTO "template_twin_release_attestation_keys" (
        "keyId", "purpose", "secret", "principalUserId",
        "effectiveAt", "expiresAt"
      ) VALUES (
        ${replacementRuntime.runtimeKeyId}, 'RUNTIME', ${signingSecret}, NULL,
        ${new Date(now - 60_000)}, ${new Date(now + 12 * 60 * 60 * 1_000)}
      )
    `);
    const replacementKeyControl = {
      ...active.control,
      phase: "REPLACEMENT_KEY_CREATED",
      releaseOrdinal,
      cohort,
      authorizedPracticeIds,
      supersedesReleaseId: active.control.releaseId,
      supersededReleases,
      globalGeneration: revoked.globalGeneration.toString(),
      appInstanceId: replacementRuntime.appInstanceId,
      workerInstanceId: replacementRuntime.workerInstanceId,
      runtimeKeyId: replacementRuntime.runtimeKeyId,
      runtimeSigningSecret: Buffer.from(signingSecret).toString("base64url"),
      checkpointStatus: "PENDING",
    } as const;
    persistLifecycleCheckpoint({
      boundary,
      status: "REPLACEMENT_KEY_CREATED",
      control: replacementKeyControl,
      identitiesContents: active.identitiesContents,
      runtimeContents: disabledRuntimeContents,
    });

    const reviewers = await loadSyntheticReviewerActors(owner);
    const evidence = syntheticEvidence(boundary);
    const created = await releaseControl.createTemplateTwinReleaseCandidate({
      actor: active.control.creator,
      confirmation: "CREATE EXACT RELEASE",
      evidence,
      guardrailPolicy: syntheticGuardrailPolicy(),
      authorizedPracticeIds,
      canaryPracticeIds: authorizedPracticeIds,
      runtimeInstances: [
        {
          instanceId: replacementRuntime.appInstanceId,
          component: "APP",
          imageDigest: evidence.appImageDigest,
        },
        {
          instanceId: replacementRuntime.workerInstanceId,
          component: "WORKER",
          imageDigest: evidence.workerImageDigest,
        },
      ],
    });
    if (
      created.releaseIdentitySha256 === active.control.releaseIdentitySha256
    ) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_IDENTITY_NOT_REPLACED");
    }
    let releaseGeneration = created.generation;
    const replacementControl = {
      ...replacementKeyControl,
      phase: "REPLACEMENT_CREATED",
      preparedAtEpochSeconds: Math.floor(Date.now() / 1_000),
      releaseId: created.releaseId,
      releaseIdentitySha256: created.releaseIdentitySha256,
      releaseGeneration,
      appRuntimeAttestationNonceSha256: sha256(
        `replacement-app-not-issued-${releaseOrdinal}`,
      ),
      workerRuntimeAttestationNonceSha256: sha256(
        `replacement-worker-not-issued-${releaseOrdinal}`,
      ),
    } as const;
    persistLifecycleCheckpoint({
      boundary,
      status: "REPLACEMENT_CREATED",
      control: replacementControl,
      identitiesContents: active.identitiesContents,
      runtimeContents: disabledRuntimeContents,
    });

    releaseGeneration = (
      await releaseControl.freezeTemplateTwinReleaseCandidate({
        actor: active.control.creator,
        releaseId: created.releaseId,
        expectedReleaseGeneration: releaseGeneration,
        confirmation: `FREEZE ${created.releaseIdentitySha256.slice(0, 12)}`,
      })
    ).generation;
    persistLifecycleCheckpoint({
      boundary,
      status: "REPLACEMENT_FROZEN",
      control: {
        ...replacementControl,
        phase: "REPLACEMENT_FROZEN",
        releaseGeneration,
      },
      identitiesContents: active.identitiesContents,
      runtimeContents: disabledRuntimeContents,
    });

    const approvalEvidenceSha256 = sha256(SYNTHETIC_APPROVAL_EVIDENCE_LABEL);
    for (const discipline of TEMPLATE_TWIN_RELEASE_DISCIPLINES) {
      const approval = await releaseControl.recordTemplateTwinReleaseApproval({
        actor: reviewers.get(discipline)!,
        releaseId: created.releaseId,
        expectedReleaseGeneration: releaseGeneration,
        discipline,
        decision: "APPROVE",
        evidenceSha256: approvalEvidenceSha256,
        confirmation: templateTwinApprovalConfirmation({
          decision: "APPROVE",
          discipline,
          releaseIdentitySha256: created.releaseIdentitySha256,
        }),
      });
      releaseGeneration = approval.generation;
      persistLifecycleCheckpoint({
        boundary,
        status: `REPLACEMENT_APPROVAL_${discipline}`,
        control: {
          ...replacementControl,
          phase: `REPLACEMENT_APPROVAL_${discipline}`,
          releaseGeneration,
        },
        identitiesContents: active.identitiesContents,
        runtimeContents: disabledRuntimeContents,
      });
    }

    const issuedAtEpochSeconds = Math.floor(Date.now() / 1_000) - 1;
    const expiresAtEpochSeconds = issuedAtEpochSeconds + 4 * 60 * 60;
    const commonEnvelope = {
      keyId: replacementRuntime.runtimeKeyId,
      signingSecret,
      releaseIdentitySha256: created.releaseIdentitySha256,
      sourceCommitSha: evidence.sourceCommitSha,
      appImageDigest: evidence.appImageDigest,
      workerImageDigest: evidence.workerImageDigest,
      issuedAtEpochSeconds,
      expiresAtEpochSeconds,
    } as const;
    const appRuntimeAttestationNonce = randomUUID();
    const workerRuntimeAttestationNonce = randomUUID();
    const appRuntimeAttestation = buildSyntheticRuntimeEnvelope({
      ...commonEnvelope,
      instanceId: replacementRuntime.appInstanceId,
      component: "APP",
      nonce: appRuntimeAttestationNonce,
    });
    const workerRuntimeAttestation = buildSyntheticRuntimeEnvelope({
      ...commonEnvelope,
      instanceId: replacementRuntime.workerInstanceId,
      component: "WORKER",
      nonce: workerRuntimeAttestationNonce,
    });
    assert.notEqual(appRuntimeAttestation, workerRuntimeAttestation);
    const runtimeContents = serializeSyntheticRuntimeEnvironment({
      killSwitch: "true",
      releaseIdentitySha256: created.releaseIdentitySha256,
      sourceCommitSha: evidence.sourceCommitSha,
      appImageDigest: evidence.appImageDigest,
      workerImageDigest: evidence.workerImageDigest,
      migratorImageDigest: evidence.migratorImageDigest,
      appInstanceId: replacementRuntime.appInstanceId,
      workerInstanceId: replacementRuntime.workerInstanceId,
      appRuntimeAttestation,
      workerRuntimeAttestation,
    });
    const readinessRows = await owner.$queryRaw<Array<{ ready: boolean }>>(
      Prisma.sql`
        SELECT template_twin_release_runtime_ready(
          ${created.releaseId}::UUID,
          ${created.releaseIdentitySha256}::CHAR(64)
        ) AS "ready"
      `,
    );
    if (readinessRows[0]?.ready !== false) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_PREMATURE_READINESS");
    }
    const control: PreparedControlDocument = {
      ...replacementControl,
      phase: "REPLACEMENT_PREPARED",
      preparedAtEpochSeconds: Math.floor(Date.now() / 1_000),
      releaseGeneration,
      appRuntimeAttestationNonceSha256: sha256(appRuntimeAttestationNonce),
      workerRuntimeAttestationNonceSha256: sha256(
        workerRuntimeAttestationNonce,
      ),
    };
    persistLifecycleCheckpoint({
      boundary,
      status: "REPLACEMENT_PREPARED",
      control,
      identitiesContents: active.identitiesContents,
      runtimeContents,
    });
    publishSafeGithubEnvironment(boundary);
  } finally {
    await Promise.all([
      owner.$disconnect(),
      runtimePrincipalProbe.$disconnect(),
      releaseControlDatabase?.$disconnect(),
    ]);
  }
}

async function revokeFixture(
  boundary: SyntheticReleaseFixtureBoundary,
): Promise<void> {
  const current = parseFinalLifecycleDocuments(boundary, [
    "PREPARED",
    "ACTIVE",
    "REPLACEMENT_PREPARED",
    "REVOKED",
    "CLEANED",
  ]);
  const disabledRuntimeContents = runtimeEnvironmentForControl({
    control: current.control,
    runtimeContents: current.runtimeContents,
    killSwitch: "true",
  });
  if (disabledRuntimeContents !== current.runtimeContents) {
    // Publish the process-level kill switch before touching persisted rollout
    // authority. An interruption from this point is disabled and recoverable.
    replacePrivateFileAtomically(
      boundary,
      "runtime.env",
      disabledRuntimeContents,
    );
  }

  process.env.NODE_ENV = "test";
  process.env.TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL =
    boundary.releaseControlDatabaseUrl;
  process.env.TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL =
    boundary.releaseControlDatabaseUrl;
  const owner = client(boundary.ownerDatabaseUrl);
  const runtimePrincipalProbe = client(boundary.runtimeDatabaseUrl);
  let releaseControlDatabase: PrismaClient | undefined;
  try {
    const [releaseControl, releaseControlDb] = await Promise.all([
      import("../../../apps/transcribe-md/src/lib/template-twin/release-control"),
      import("../../../apps/transcribe-md/src/lib/template-twin/release-control-db"),
    ]);
    releaseControlDatabase = releaseControlDb.default as PrismaClient;
    await Promise.all([
      assertDatabaseIdentity(owner, "meddoc"),
      assertDatabaseIdentity(releaseControlDatabase, "meddoc_release_control"),
      assertDatabaseIdentity(runtimePrincipalProbe, "meddoc_runtime"),
    ]);
    const before = await readReleaseControlState(
      owner,
      current.control.releaseId,
    );
    if (
      ["FROZEN", "APPROVED", "ROLLING_OUT", "STABLE_100"].includes(
        before.releaseStatus,
      )
    ) {
      await releaseControl.revokeTemplateTwinRelease({
        actor: current.control.creator,
        releaseId: current.control.releaseId,
        expectedReleaseGeneration: before.releaseGeneration.toString(),
        expectedGlobalGeneration: before.globalGeneration.toString(),
        reasonCode: "SYNTHETIC_CI_FIXTURE_CLEANUP",
        confirmation: `REVOKE ${current.control.releaseIdentitySha256.slice(0, 12)}`,
      });
    } else if (before.releaseStatus !== "REVOKED") {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_CONTROL_INVALID");
    }

    await owner.$executeRaw(Prisma.sql`
      UPDATE "template_twin_release_attestation_keys"
      SET "revokedAt" = CURRENT_TIMESTAMP
      WHERE "keyId" = ${current.control.runtimeKeyId}
        AND "purpose" = 'RUNTIME' AND "revokedAt" IS NULL
    `);
    const after = await readReleaseControlState(
      owner,
      current.control.releaseId,
    );
    const expectedRuntimeKeyIds = [
      ...current.control.supersededReleases.map(
        ({ runtimeKeyId }) => runtimeKeyId,
      ),
      current.control.runtimeKeyId,
    ];
    const keyRows = await owner.$queryRaw<
      Array<{ keyId: string; revoked: boolean }>
    >(
      Prisma.sql`
        SELECT "keyId", "revokedAt" IS NOT NULL AS "revoked"
        FROM "template_twin_release_attestation_keys"
        WHERE "keyId" IN (${Prisma.join(expectedRuntimeKeyIds)})
          AND "purpose" = 'RUNTIME'
        ORDER BY "keyId"
      `,
    );
    await assertSyntheticPracticeExposure(owner, []);
    if (
      after.enabled ||
      after.releaseStatus !== "REVOKED" ||
      !["PENDING", "REVOKED"].includes(after.checkpointStatus) ||
      keyRows.length !== expectedRuntimeKeyIds.length ||
      keyRows.some(
        ({ keyId, revoked }) =>
          !expectedRuntimeKeyIds.includes(keyId) || revoked !== true,
      )
    ) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_CONTROL_INVALID");
    }
    const phase = current.control.phase === "CLEANED" ? "CLEANED" : "REVOKED";
    persistLifecycleCheckpoint({
      boundary,
      status: phase,
      control: {
        ...current.control,
        phase,
        releaseGeneration: after.releaseGeneration.toString(),
        globalGeneration: after.globalGeneration.toString(),
        checkpointStatus: after.checkpointStatus as
          | "PENDING"
          | "ACTIVE"
          | "REVOKED",
      } satisfies PreparedControlDocument,
      identitiesContents: current.identitiesContents,
      runtimeContents: disabledRuntimeContents,
    });
  } finally {
    await Promise.all([
      owner.$disconnect(),
      runtimePrincipalProbe.$disconnect(),
      releaseControlDatabase?.$disconnect(),
    ]);
  }
}

async function cleanupInterruptedFixture(
  boundary: SyntheticReleaseFixtureBoundary,
): Promise<void> {
  const interruptedDisabledRuntimeContents =
    "QA_TEMPLATE_TWIN_KILL_SWITCH=true\n";
  publishOrReplacePrivateFile(
    boundary,
    "runtime.env",
    interruptedDisabledRuntimeContents,
  );
  const controlPath = privateFilePath(boundary, "release-control.json");
  const statePath = privateFilePath(boundary, "state.json");
  const identitiesPath = privateFilePath(boundary, "fixture-identities.json");
  let partialControl: Record<string, unknown> | undefined;
  if (existsSync(controlPath)) {
    let value: unknown;
    try {
      value = JSON.parse(readPrivateFile(boundary, "release-control.json"));
    } catch {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_STATE_INVALID");
    }
    if (
      !isRecord(value) ||
      value.version !== FIXTURE_VERSION ||
      value.profile !== SYNTHETIC_RELEASE_FIXTURE_PROFILE ||
      value.synthetic !== true ||
      value.productionHumanApprovals !== "NOT_EVALUATED" ||
      value.approvalEvidenceLabel !== SYNTHETIC_APPROVAL_EVIDENCE_LABEL ||
      value.runId !== boundary.runId ||
      value.runAttempt !== boundary.runAttempt ||
      value.sourceCommitSha !== boundary.sourceCommitSha ||
      value.appImageDigest !== boundary.appImageDigest ||
      value.workerImageDigest !== boundary.workerImageDigest ||
      value.migratorImageDigest !== boundary.migratorImageDigest
    ) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_STATE_INVALID");
    }
    partialControl = value;
  }
  if (existsSync(statePath)) {
    let value: unknown;
    try {
      value = JSON.parse(readPrivateFile(boundary, "state.json"));
    } catch {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_STATE_INVALID");
    }
    if (
      !isRecord(value) ||
      value.version !== FIXTURE_VERSION ||
      value.profile !== SYNTHETIC_RELEASE_FIXTURE_PROFILE ||
      value.productionHumanApprovals !== "NOT_EVALUATED"
    ) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_STATE_INVALID");
    }
  }
  const identitiesContents = existsSync(identitiesPath)
    ? readPrivateFile(boundary, "fixture-identities.json")
    : jsonDocument({
        version: FIXTURE_VERSION,
        profile: SYNTHETIC_RELEASE_FIXTURE_PROFILE,
        synthetic: true,
        phi: "FORBIDDEN",
        productionUse: "FORBIDDEN",
        credentials: "UNAVAILABLE_AFTER_INTERRUPTED_PREPARE",
      });

  process.env.NODE_ENV = "test";
  process.env.TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL =
    boundary.releaseControlDatabaseUrl;
  process.env.TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL =
    boundary.releaseControlDatabaseUrl;
  const owner = client(boundary.ownerDatabaseUrl);
  const runtimePrincipalProbe = client(boundary.runtimeDatabaseUrl);
  let releaseControlDatabase: PrismaClient | undefined;
  try {
    const [releaseControl, releaseControlDb] = await Promise.all([
      import("../../../apps/transcribe-md/src/lib/template-twin/release-control"),
      import("../../../apps/transcribe-md/src/lib/template-twin/release-control-db"),
    ]);
    releaseControlDatabase = releaseControlDb.default as PrismaClient;
    await Promise.all([
      assertDatabaseIdentity(owner, "meddoc"),
      assertDatabaseIdentity(releaseControlDatabase, "meddoc_release_control"),
      assertDatabaseIdentity(runtimePrincipalProbe, "meddoc_runtime"),
    ]);
    const candidates = await owner.$queryRaw<
      Array<{
        id: string;
        releaseIdentitySha256: string;
        status: string;
        generation: bigint;
      }>
    >(Prisma.sql`
      SELECT "id"::TEXT, "releaseIdentitySha256", "status", "generation"
      FROM "template_twin_release_candidates"
      WHERE "createdById" =
        ${SYNTHETIC_FIXTURE_IDENTITIES.administrator.creatorId}
        AND "sourceCommitSha" = ${boundary.sourceCommitSha}::CHAR(40)
        AND "appImageDigest" = ${boundary.appImageDigest}
        AND "workerImageDigest" = ${boundary.workerImageDigest}
        AND "migratorImageDigest" = ${boundary.migratorImageDigest}
      ORDER BY "createdAt"
    `);
    if (candidates.length > 99) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_CONTROL_INVALID");
    }
    const nonterminalCandidates = candidates.filter(
      ({ status }) => status !== "REVOKED",
    );
    if (nonterminalCandidates.length > 1) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_CONTROL_INVALID");
    }
    const candidate = nonterminalCandidates[0];
    const globalRows = await owner.$queryRaw<
      Array<{ enabled: boolean; generation: bigint }>
    >(Prisma.sql`
      SELECT "enabled", "generation" FROM "template_twin_rollout_controls"
      WHERE "id" = 'global'
    `);
    const global = globalRows[0];
    if (!global) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_CONTROL_INVALID");
    }
    if (
      candidate &&
      ["FROZEN", "APPROVED", "ROLLING_OUT", "STABLE_100"].includes(
        candidate.status,
      )
    ) {
      const session = await owner.userSession.findFirst({
        where: {
          userId: SYNTHETIC_FIXTURE_IDENTITIES.administrator.creatorId,
          expiresAt: { gt: new Date() },
        },
        select: { sessionToken: true },
        orderBy: { createdAt: "desc" },
      });
      if (!session) {
        fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_AUTHORITY_INVALID");
      }
      await releaseControl.revokeTemplateTwinRelease({
        actor: {
          userId: SYNTHETIC_FIXTURE_IDENTITIES.administrator.creatorId,
          sessionId: session.sessionToken,
        },
        releaseId: candidate.id,
        expectedReleaseGeneration: candidate.generation.toString(),
        expectedGlobalGeneration: global.generation.toString(),
        reasonCode: "SYNTHETIC_CI_FIXTURE_INTERRUPTED",
        confirmation: `REVOKE ${candidate.releaseIdentitySha256.slice(0, 12)}`,
      });
    } else if (candidate && !["DRAFT", "REVOKED"].includes(candidate.status)) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_CONTROL_INVALID");
    }

    const runtimeKeyPattern =
      `^synthetic-ci-runtime-${boundary.runId}-${boundary.runAttempt}-` +
      "r([1-9][0-9]?)$";
    await owner.$executeRaw(Prisma.sql`
      UPDATE "template_twin_release_attestation_keys"
      SET "revokedAt" = CURRENT_TIMESTAMP
      WHERE "keyId" ~ ${runtimeKeyPattern}
        AND "purpose" = 'RUNTIME' AND "revokedAt" IS NULL
    `);
    const reviewerIds = TEMPLATE_TWIN_RELEASE_DISCIPLINES.map(
      (discipline) =>
        `synthetic_ci_template_twin_reviewer_${discipline.toLowerCase()}`,
    );
    const userIds = [
      SYNTHETIC_FIXTURE_IDENTITIES.administrator.creatorId,
      SYNTHETIC_FIXTURE_IDENTITIES.infrastructure.doctorId,
      SYNTHETIC_FIXTURE_IDENTITIES.stagingPrimary.doctorId,
      SYNTHETIC_FIXTURE_IDENTITIES.stagingForeign.doctorId,
      ...reviewerIds,
    ];
    await owner.$transaction(async (tx) => {
      await tx.userSession.deleteMany({ where: { userId: { in: userIds } } });
      await tx.user.updateMany({
        where: { id: { in: userIds }, isActive: true },
        data: { isActive: false, deactivatedAt: new Date() },
      });
    });
    const verificationRows = await owner.$queryRaw<
      Array<{
        enabled: boolean;
        activePractices: bigint;
        activeUsers: bigint;
        liveSessions: bigint;
        liveKeys: bigint;
      }>
    >(Prisma.sql`
      SELECT control."enabled",
        (
          SELECT COUNT(*)::BIGINT FROM "practices" practice
          WHERE practice."id" IN (${Prisma.join(allFixturePracticeIds)})
            AND practice."templateTwinEnabled"
        ) AS "activePractices",
        (
          SELECT COUNT(*)::BIGINT FROM "users" account
          WHERE account."id" IN (${Prisma.join(userIds)})
            AND account."isActive"
        ) AS "activeUsers",
        (
          SELECT COUNT(*)::BIGINT FROM "user_sessions" session
          WHERE session."userId" IN (${Prisma.join(userIds)})
        ) AS "liveSessions",
        (
          SELECT COUNT(*)::BIGINT
          FROM "template_twin_release_attestation_keys" key
          WHERE key."keyId" ~ ${runtimeKeyPattern}
            AND key."revokedAt" IS NULL
        ) AS "liveKeys"
      FROM "template_twin_rollout_controls" control
      WHERE control."id" = 'global'
    `);
    const verification = verificationRows[0];
    if (
      !verification ||
      verification.enabled ||
      verification.activePractices !== BigInt(0) ||
      verification.activeUsers !== BigInt(0) ||
      verification.liveSessions !== BigInt(0) ||
      verification.liveKeys !== BigInt(0)
    ) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_CLEANUP_INCOMPLETE");
    }
    persistLifecycleCheckpoint({
      boundary,
      status: "PARTIAL_CLEANED",
      control: {
        version: FIXTURE_VERSION,
        profile: SYNTHETIC_RELEASE_FIXTURE_PROFILE,
        phase: "PARTIAL_CLEANED",
        synthetic: true,
        productionHumanApprovals: "NOT_EVALUATED",
        approvalEvidenceLabel: SYNTHETIC_APPROVAL_EVIDENCE_LABEL,
        runId: boundary.runId,
        runAttempt: boundary.runAttempt,
        sourceCommitSha: boundary.sourceCommitSha,
        appImageDigest: boundary.appImageDigest,
        workerImageDigest: boundary.workerImageDigest,
        migratorImageDigest: boundary.migratorImageDigest,
        releaseIds: candidates.map(({ id }) => id),
        releaseDisposition:
          candidate?.status === "DRAFT"
            ? "DRAFT_DISABLED_DISPOSABLE_DATABASE_REQUIRED"
            : candidate
              ? "REVOKED"
              : candidates.length > 0
                ? "ALL_REVOKED"
                : "NOT_CREATED",
        previousLifecyclePhase: partialControl?.phase ?? "DIRECTORY_ONLY",
      },
      identitiesContents,
      runtimeContents: interruptedDisabledRuntimeContents,
    });
  } finally {
    await Promise.all([
      owner.$disconnect(),
      runtimePrincipalProbe.$disconnect(),
      releaseControlDatabase?.$disconnect(),
    ]);
  }
}

async function cleanupFixture(
  boundary: SyntheticReleaseFixtureBoundary,
): Promise<void> {
  try {
    readFinalLifecyclePhase(boundary);
  } catch {
    await cleanupInterruptedFixture(boundary);
    return;
  }
  await revokeFixture(boundary);
  const revoked = parseFinalLifecycleDocuments(boundary, [
    "REVOKED",
    "CLEANED",
  ]);
  const owner = client(boundary.ownerDatabaseUrl);
  try {
    await assertDatabaseIdentity(owner, "meddoc");
    const reviewerIds = TEMPLATE_TWIN_RELEASE_DISCIPLINES.map(
      (discipline) =>
        `synthetic_ci_template_twin_reviewer_${discipline.toLowerCase()}`,
    );
    const userIds = [
      SYNTHETIC_FIXTURE_IDENTITIES.administrator.creatorId,
      SYNTHETIC_FIXTURE_IDENTITIES.infrastructure.doctorId,
      SYNTHETIC_FIXTURE_IDENTITIES.stagingPrimary.doctorId,
      SYNTHETIC_FIXTURE_IDENTITIES.stagingForeign.doctorId,
      ...reviewerIds,
    ];
    await owner.$transaction(async (tx) => {
      await tx.userSession.deleteMany({ where: { userId: { in: userIds } } });
      await tx.user.updateMany({
        where: { id: { in: userIds }, isActive: true },
        data: { isActive: false, deactivatedAt: new Date() },
      });
    });
    const residueRows = await owner.$queryRaw<
      Array<{ activeUsers: bigint; liveSessions: bigint }>
    >(Prisma.sql`
      SELECT
        COUNT(*) FILTER (WHERE account."isActive")::BIGINT AS "activeUsers",
        (
          SELECT COUNT(*)::BIGINT FROM "user_sessions" session
          WHERE session."userId" IN (${Prisma.join(userIds)})
        ) AS "liveSessions"
      FROM "users" account
      WHERE account."id" IN (${Prisma.join(userIds)})
    `);
    if (
      residueRows[0]?.activeUsers !== BigInt(0) ||
      residueRows[0]?.liveSessions !== BigInt(0)
    ) {
      fail("TEMPLATE_TWIN_SYNTHETIC_CI_RELEASE_FIXTURE_CLEANUP_INCOMPLETE");
    }
    persistLifecycleCheckpoint({
      boundary,
      status: "CLEANED",
      control: {
        ...revoked.control,
        phase: "CLEANED",
      } satisfies PreparedControlDocument,
      identitiesContents: revoked.identitiesContents,
      runtimeContents: revoked.runtimeContents,
    });
  } finally {
    await owner.$disconnect();
  }
}

export async function runSyntheticReleaseFixture(
  phase: SyntheticReleaseFixturePhase,
  environment: Environment = process.env,
): Promise<void> {
  const boundary = validateSyntheticReleaseFixtureBoundary(environment);
  assertFilesystemBoundary(boundary, phase);
  switch (phase) {
    case "prepare":
      await prepareFixture(boundary);
      return;
    case "activate":
      await activateFixture(boundary);
      return;
    case "replace":
      await prepareReplacementFixture(boundary);
      return;
    case "revoke":
      await revokeFixture(boundary);
      return;
    case "cleanup":
      await cleanupFixture(boundary);
      return;
  }
}

const isCli =
  process.argv[1] !== undefined &&
  resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));

if (isCli) {
  let phase: SyntheticReleaseFixturePhase;
  try {
    phase = parseSyntheticReleaseFixturePhase(process.argv.slice(2));
  } catch {
    process.stderr.write(`${SAFE_FAILURE}\n`);
    process.exitCode = 1;
    phase = "prepare";
  }
  if (process.exitCode === undefined)
    void runSyntheticReleaseFixture(phase, process.env)
      .then(() => {
        process.stdout.write(`${JSON.stringify(SAFE_SUCCESS[phase])}\n`);
      })
      .catch(() => {
        process.stderr.write(`${SAFE_FAILURE}\n`);
        process.exitCode = 1;
      });
}
