#!/usr/bin/env tsx

// GitHub Actions-only disposable database provisioner. It accepts no target,
// image, credential, or database-name input: every invocation creates a new
// hard-coded marker-named PostgreSQL database on the local Docker daemon,
// applies the same witnessed segmented release protocol as production, and
// exports only job-scoped runtime channels through GITHUB_ENV.

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import {
  chmodSync,
  existsSync,
  lstatSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
  writeSync,
} from "node:fs";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

type Phase = "provision" | "cleanup";

export interface SyntheticState {
  version: "quillmd-synthetic-ci-database-state-v1";
  token: string;
  containerName: string;
  volumeName: string;
  imageTag: string;
  temporaryDirectory: string;
  ready: boolean;
}

interface CommandOptions {
  environment?: NodeJS.ProcessEnv;
  input?: string;
  inheritOutput?: boolean;
  tolerateFailure?: boolean;
  timeoutMs?: number;
}

type JsonObject = Record<string, unknown>;

export interface SyntheticDatabaseSecrets {
  readonly owner: string;
  readonly runtime: string;
  readonly releaseControl: string;
  readonly releaseSecurity: string;
  readonly auditDispatcher: string;
  readonly authEmailDispatcher: string;
  readonly backup: string;
}

type GithubWorkflowCommandWriter = (command: string) => void;

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(packageRoot, "../..");
const syntheticDatabase = "meddoc_ci_test";
const databaseOwner = "meddoc";
const requiredAcknowledgement = "isolated-disposable-v1";
const stateFileName = "quillmd-synthetic-ci-database-state-v1.json";
const containerPrefix = "quillmd-synthetic-ci-postgres-";
const volumePrefix = "quillmd-synthetic-ci-pgdata-";
const imagePrefix = "quillmd-synthetic-ci-postgres:";
const syntheticNodeImage =
  "node:22-bookworm@sha256:175215a1f306ed5df592434b99cc2019f70624373fe49cb659240a618a846aed";
const resourceLabel = "com.quillmd.synthetic-ci-release";
const resourceLabelVersion = "v1";
const startupContractSha256 =
  "8b76fed3fc6791617a828fcf5f1cbff35d681d3e753cda9594c89df52ea929b0";
const canonicalOptions = "-c%20search_path%3Dpg_catalog%2Cpublic";
const forbiddenAmbientRouting = [
  "DATABASE_URL",
  "DOCKER_CONTEXT",
  "DOCKER_HOST",
  "PGDATABASE",
  "PGHOST",
  "PGHOSTADDR",
  "PGOPTIONS",
  "PGPASSFILE",
  "PGPASSWORD",
  "PGPORT",
  "PGSERVICE",
  "PGSERVICEFILE",
  "PGUSER",
  "QUILLMD_POSTGRES_IMAGE",
  "DATABASE_RELEASE_MIGRATION_ALLOW_PRODUCTION",
  "DATABASE_RELEASE_MIGRATION_PRODUCTION_ACK",
  "DATABASE_RELEASE_MIGRATION_PRODUCTION_CHANGE_ID",
  "TEMPLATE_TWIN_LINEAGE_ALLOW_PRODUCTION",
  "TEMPLATE_TWIN_LINEAGE_PRODUCTION_ACK",
  "TEMPLATE_TWIN_LINEAGE_PRODUCTION_CHANGE_ID",
  "AUTH_TOKEN_LINEARIZATION_ALLOW_PRODUCTION",
  "AUTH_TOKEN_LINEARIZATION_PRODUCTION_ACK",
  "AUTH_TOKEN_LINEARIZATION_PRODUCTION_CHANGE_ID",
] as const;

function fail(code: string): never {
  throw new Error(code);
}

function command(
  executable: string,
  args: readonly string[],
  code: string,
  options: CommandOptions = {},
): string {
  const result = spawnSync(executable, [...args], {
    cwd: repositoryRoot,
    encoding: "utf8",
    input: options.input,
    maxBuffer: 32 * 1024 * 1024,
    timeout: options.timeoutMs ?? 20 * 60_000,
    env: options.environment,
    ...(options.inheritOutput ? { stdio: "inherit" as const } : {}),
  });
  if (result.error || result.signal !== null || result.status !== 0) {
    if (options.tolerateFailure) return "";
    const safeChildCode =
      typeof result.stderr === "string"
        ? result.stderr
            .split(/\r?\n/u)
            .map((line) => line.trim())
            .find((line) =>
              /^(?:DATABASE_RELEASE_MIGRATION|LINEAGE_MIGRATION|AUTH_TOKEN_LINEARIZATION|EXACT_DATABASE_PRINCIPAL)_[A-Z0-9_]{2,120}$/u.test(
                line,
              ),
            )
        : undefined;
    if (safeChildCode) {
      fail(`SYNTHETIC_CI_DATABASE_RELEASE_CHILD_${safeChildCode}`);
    }
    fail(code);
  }
  return typeof result.stdout === "string" ? result.stdout.trim() : "";
}

function dockerEnvironment(extra: NodeJS.ProcessEnv = {}): NodeJS.ProcessEnv {
  return {
    PATH: process.env.PATH,
    HOME: process.env.HOME,
    NO_COLOR: "1",
    ...extra,
  };
}

function parsePhase(args: readonly string[]): Phase {
  if (
    args.length !== 2 ||
    args[0] !== "--phase" ||
    (args[1] !== "provision" && args[1] !== "cleanup")
  ) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_PHASE_INVALID");
  }
  return args[1];
}

function requiredRunnerPath(name: "RUNNER_TEMP" | "GITHUB_ENV"): string {
  const value = process.env[name];
  if (!value || !isAbsolute(value)) {
    fail(`SYNTHETIC_CI_DATABASE_RELEASE_${name}_INVALID`);
  }
  return resolve(value);
}

function assertSyntheticCiBoundary(phase: Phase): {
  runnerTemp: string;
  githubEnvironment: string;
  statePath: string;
} {
  if (
    process.env.GITHUB_ACTIONS !== "true" ||
    process.env.CI !== "true" ||
    process.env.QUILLMD_SYNTHETIC_CI_DATABASE_RELEASE !==
      requiredAcknowledgement
  ) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_BOUNDARY_REQUIRED");
  }
  if (phase === "provision") {
    for (const name of forbiddenAmbientRouting) {
      if (process.env[name] !== undefined) {
        fail("SYNTHETIC_CI_DATABASE_RELEASE_AMBIENT_ROUTE_REFUSED");
      }
    }
  }
  const runnerTemp = requiredRunnerPath("RUNNER_TEMP");
  const githubEnvironment = requiredRunnerPath("GITHUB_ENV");
  const expectedGithubEnvironmentPrefix = join(
    runnerTemp,
    "_runner_file_commands",
    "set_env_",
  );
  if (!githubEnvironment.startsWith(expectedGithubEnvironmentPrefix)) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_GITHUB_ENV_INVALID");
  }
  const statePath = join(runnerTemp, stateFileName);
  const dockerEndpoint = command(
    "docker",
    ["context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
    "SYNTHETIC_CI_DATABASE_RELEASE_DOCKER_CONTEXT_FAILED",
    { environment: dockerEnvironment() },
  );
  if (dockerEndpoint !== "unix:///var/run/docker.sock") {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_LOCAL_DOCKER_REQUIRED");
  }
  return { runnerTemp, githubEnvironment, statePath };
}

function randomSecret(): string {
  const value = randomBytes(32).toString("base64url");
  assert.match(value, /^[A-Za-z0-9_-]{43}$/u);
  return value;
}

function writeGithubWorkflowCommand(command: string): void {
  const expectedBytes = Buffer.byteLength(command);
  if (writeSync(1, command) !== expectedBytes) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_SECRET_MASK_WRITE_FAILED");
  }
}

function escapeGithubWorkflowCommandData(value: string): string {
  return value.replaceAll("%", "%25");
}

export function registerGithubSecretMasks(
  values: readonly unknown[],
  writeCommand: GithubWorkflowCommandWriter = writeGithubWorkflowCommand,
): void {
  const distinctValues: string[] = [];
  const seen = new Set<string>();

  // Validate the complete batch before emitting a partial masking contract.
  // Failure codes intentionally contain no caller-supplied value.
  for (const value of values) {
    if (
      typeof value !== "string" ||
      value.length === 0 ||
      /[\r\n]/u.test(value)
    ) {
      fail("SYNTHETIC_CI_DATABASE_RELEASE_SECRET_MASK_INVALID");
    }
    if (!seen.has(value)) {
      seen.add(value);
      distinctValues.push(value);
    }
  }

  for (const value of distinctValues) {
    try {
      writeCommand(`::add-mask::${escapeGithubWorkflowCommandData(value)}\n`);
    } catch {
      fail("SYNTHETIC_CI_DATABASE_RELEASE_SECRET_MASK_WRITE_FAILED");
    }
  }
}

export function generateMaskedSyntheticDatabaseSecrets(
  writeCommand: GithubWorkflowCommandWriter = writeGithubWorkflowCommand,
): SyntheticDatabaseSecrets {
  const secrets: SyntheticDatabaseSecrets = Object.freeze({
    owner: randomSecret(),
    runtime: randomSecret(),
    releaseControl: randomSecret(),
    releaseSecurity: randomSecret(),
    auditDispatcher: randomSecret(),
    authEmailDispatcher: randomSecret(),
    backup: randomSecret(),
  });
  const values = Object.values(secrets);
  if (new Set(values).size !== values.length) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_SECRET_COLLISION");
  }
  registerGithubSecretMasks(values, writeCommand);
  return secrets;
}

function internalDatabaseUrl(login: string, secret: string): string {
  return `postgresql://${login}:${secret}@127.0.0.1:5432/${syntheticDatabase}?schema=public&options=${canonicalOptions}`;
}

function externalDatabaseUrl(
  login: string,
  secret: string,
  port: number,
): string {
  return `postgresql://${login}:${secret}@127.0.0.1:${port}/${syntheticDatabase}?schema=public&options=${canonicalOptions}`;
}

function exactJsonLines(output: string): JsonObject[] {
  const values: JsonObject[] = [];
  for (const line of output.split(/\r?\n/u)) {
    const candidate = line.trim();
    if (!candidate.startsWith("{") || !candidate.endsWith("}")) continue;
    try {
      const parsed: unknown = JSON.parse(candidate);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        values.push(parsed as JsonObject);
      }
    } catch {
      // npm may emit non-JSON diagnostics; protocol records remain exact JSON.
    }
  }
  return values;
}

function lastJson(output: string, code: string): JsonObject {
  const value = exactJsonLines(output).at(-1);
  if (!value) fail(code);
  return value;
}

function requiredFingerprint(value: unknown, code: string): string {
  if (typeof value !== "string" || !/^[a-f0-9]{64}$/u.test(value)) {
    fail(code);
  }
  return value;
}

function objectValue(value: unknown, code: string): JsonObject {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(code);
  return value as JsonObject;
}

function writeState(path: string, state: SyntheticState): void {
  writeFileSync(path, `${JSON.stringify(state)}\n`, {
    encoding: "utf8",
    mode: 0o600,
  });
  chmodSync(path, 0o600);
}

function validateState(value: unknown, runnerTemp: string): SyntheticState {
  const state = objectValue(
    value,
    "SYNTHETIC_CI_DATABASE_RELEASE_STATE_INVALID",
  ) as unknown as SyntheticState;
  const expectedTemporaryDirectory = join(
    runnerTemp,
    `quillmd-synthetic-ci-${state.token}`,
  );
  if (
    state.version !== "quillmd-synthetic-ci-database-state-v1" ||
    !/^[a-f0-9]{24}$/u.test(state.token) ||
    state.containerName !== `${containerPrefix}${state.token}` ||
    state.volumeName !== `${volumePrefix}${state.token}` ||
    state.imageTag !== `${imagePrefix}${state.token}` ||
    resolve(state.temporaryDirectory) !== resolve(expectedTemporaryDirectory)
  ) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_STATE_INVALID");
  }
  return state;
}

interface CleanupResource {
  target: string;
  listArgs: readonly string[];
  inspectArgs: readonly string[];
  removeArgs: readonly string[];
  removeFailureCode: string;
}

function cleanupResources(state: SyntheticState): CleanupResource[] {
  const executorName = state.containerName + "-executor";
  const containerLabelFormat =
    '{{index .Config.Labels "' + resourceLabel + '"}}';
  return [
    {
      target: executorName,
      listArgs: [
        "container",
        "ls",
        "--all",
        "--filter",
        "name=^/" + executorName + "$",
        "--format",
        "{{.Names}}",
      ],
      inspectArgs: [
        "container",
        "inspect",
        "--format",
        containerLabelFormat,
        executorName,
      ],
      removeArgs: ["container", "rm", "--force", executorName],
      removeFailureCode:
        "SYNTHETIC_CI_DATABASE_RELEASE_CONTAINER_CLEANUP_FAILED",
    },
    {
      target: state.containerName,
      listArgs: [
        "container",
        "ls",
        "--all",
        "--filter",
        "name=^/" + state.containerName + "$",
        "--format",
        "{{.Names}}",
      ],
      inspectArgs: [
        "container",
        "inspect",
        "--format",
        containerLabelFormat,
        state.containerName,
      ],
      removeArgs: ["container", "rm", "--force", state.containerName],
      removeFailureCode:
        "SYNTHETIC_CI_DATABASE_RELEASE_CONTAINER_CLEANUP_FAILED",
    },
    {
      target: state.volumeName,
      listArgs: [
        "volume",
        "ls",
        "--filter",
        "name=^" + state.volumeName + "$",
        "--format",
        "{{.Name}}",
      ],
      inspectArgs: [
        "volume",
        "inspect",
        "--format",
        '{{index .Labels "' + resourceLabel + '"}}',
        state.volumeName,
      ],
      removeArgs: ["volume", "rm", state.volumeName],
      removeFailureCode: "SYNTHETIC_CI_DATABASE_RELEASE_VOLUME_CLEANUP_FAILED",
    },
    {
      target: state.imageTag,
      listArgs: [
        "image",
        "ls",
        "--all",
        "--filter",
        "reference=" + state.imageTag,
        "--format",
        "{{.Repository}}:{{.Tag}}",
      ],
      inspectArgs: [
        "image",
        "inspect",
        "--format",
        containerLabelFormat,
        state.imageTag,
      ],
      removeArgs: ["image", "rm", state.imageTag],
      removeFailureCode: "SYNTHETIC_CI_DATABASE_RELEASE_IMAGE_CLEANUP_FAILED",
    },
  ];
}

function resourceExists(resource: CleanupResource): boolean {
  const census = command(
    "docker",
    resource.listArgs,
    "SYNTHETIC_CI_DATABASE_RELEASE_RESOURCE_LIST_FAILED",
    { environment: dockerEnvironment() },
  );
  if (!census) return false;
  const names = census.split(/\r?\n/u);
  if (names.length !== 1 || names[0] !== resource.target) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_RESOURCE_CENSUS_MISMATCH");
  }
  return true;
}

function attestOwnedResource(
  resource: CleanupResource,
  expectedLabel: string,
): boolean {
  if (!resourceExists(resource)) return false;
  const label = command(
    "docker",
    resource.inspectArgs,
    "SYNTHETIC_CI_DATABASE_RELEASE_RESOURCE_INSPECTION_FAILED",
    { environment: dockerEnvironment() },
  );
  if (label !== expectedLabel) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_RESOURCE_IDENTITY_MISMATCH");
  }
  return true;
}

export function cleanupState(
  state: SyntheticState,
  runnerTemp: string,
  statePath: string,
): void {
  const expectedLabel = `${resourceLabelVersion}:${state.token}`;
  const resources = cleanupResources(state);
  // Attest every exact-name object before deleting any of them. A Docker list
  // or inspect failure, an ambiguous census, or a missing/wrong label leaves
  // the state and temporary evidence intact for operator investigation.
  const present = resources.map((resource) =>
    attestOwnedResource(resource, expectedLabel),
  );
  for (const [index, resource] of resources.entries()) {
    if (!present[index]) continue;
    command("docker", resource.removeArgs, resource.removeFailureCode, {
      environment: dockerEnvironment(),
    });
  }
  // Removal command success is not absence evidence. Prove the complete
  // exact-name resource set absent before destroying recovery state.
  for (const resource of resources) {
    if (resourceExists(resource)) {
      fail("SYNTHETIC_CI_DATABASE_RELEASE_RESOURCE_CLEANUP_INCOMPLETE");
    }
  }
  const temporaryDirectory = resolve(state.temporaryDirectory);
  const expectedPrefix = `${resolve(runnerTemp)}/quillmd-synthetic-ci-`;
  if (!temporaryDirectory.startsWith(expectedPrefix)) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_STATE_INVALID");
  }
  if (existsSync(temporaryDirectory)) {
    const metadata = lstatSync(temporaryDirectory);
    if (!metadata.isDirectory() || metadata.isSymbolicLink()) {
      fail("SYNTHETIC_CI_DATABASE_RELEASE_STATE_INVALID");
    }
    rmSync(temporaryDirectory, { recursive: true });
  }
  if (existsSync(statePath)) rmSync(statePath);
}

function runInDatabaseNetwork(
  state: SyntheticState,
  scriptPath: string,
  scriptArgs: readonly string[],
  extraEnvironment: NodeJS.ProcessEnv,
  code: string,
): string {
  if (!/^[a-z0-9_./-]+\.ts$/u.test(scriptPath) || scriptPath.includes("..")) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_SCRIPT_PATH_INVALID");
  }
  const uid = process.getuid?.();
  const gid = process.getgid?.();
  if (!Number.isSafeInteger(uid) || !Number.isSafeInteger(gid)) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_EXECUTOR_IDENTITY_INVALID");
  }
  const environment: NodeJS.ProcessEnv = {
    HOME: "/tmp",
    CI: "true",
    GITHUB_ACTIONS: "true",
    NO_COLOR: "1",
    NPM_CONFIG_UPDATE_NOTIFIER: "false",
    PRISMA_HIDE_UPDATE_MESSAGE: "1",
    ...extraEnvironment,
  };
  const environmentArgs = Object.entries(environment).flatMap(
    ([name, value]) => {
      if (!/^[A-Z][A-Z0-9_]{0,80}$/u.test(name) || value === undefined) {
        fail("SYNTHETIC_CI_DATABASE_RELEASE_EXECUTOR_ENVIRONMENT_INVALID");
      }
      return ["--env", name];
    },
  );
  const executorName = `${state.containerName}-executor`;
  const expectedLabel = `${resourceLabelVersion}:${state.token}`;
  const dockerArgs = [
    "run",
    "--rm",
    "--name",
    executorName,
    "--label",
    `${resourceLabel}=${expectedLabel}`,
    "--network",
    `container:${state.containerName}`,
    "--user",
    `${uid}:${gid}`,
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--read-only",
    "--memory",
    "1g",
    "--cpus",
    "2.0",
    "--pids-limit",
    "256",
    "--tmpfs",
    "/tmp:rw,noexec,nosuid,nodev,size=256m,mode=1777",
    "--mount",
    `type=bind,src=${repositoryRoot},dst=/workspace,readonly`,
    "--workdir",
    "/workspace",
    ...environmentArgs,
    "--entrypoint",
    "/usr/local/bin/node",
    syntheticNodeImage,
    "node_modules/tsx/dist/cli.mjs",
    scriptPath,
    ...scriptArgs,
  ];
  return command("docker", dockerArgs, code, {
    environment: dockerEnvironment(environment),
  });
}

function migrationCommand(
  state: SyntheticState,
  ownerUrl: string,
  phase: "status" | "lineage-expand" | "auth-expand" | "pre-v9" | "v9",
  approvedFingerprint?: string,
): string {
  return runInDatabaseNetwork(
    state,
    "packages/db/scripts/prisma-migrate-segment.ts",
    ["--phase", phase],
    {
      DATABASE_URL: ownerUrl,
      PRISMA_STATEMENT_TIMEOUT_MS: "30000",
      DATABASE_RELEASE_MIGRATION_LOCK_TIMEOUT_MS: "5000",
      DATABASE_RELEASE_MIGRATION_NETWORK_BOUNDARY: "postgres-loopback-v1",
      ...(approvedFingerprint
        ? {
            DATABASE_RELEASE_MIGRATION_APPROVED_TARGET_FINGERPRINT:
              approvedFingerprint,
          }
        : {}),
    },
    `SYNTHETIC_CI_DATABASE_RELEASE_SEGMENT_${phase
      .replaceAll("-", "_")
      .toUpperCase()}_FAILED`,
  );
}

function migrationStatus(
  state: SyntheticState,
  ownerUrl: string,
  count: number,
  lastMigration: string | null,
  approvalPhase: "lineage-expand" | "auth-expand" | "pre-v9" | "v9",
): string {
  const status = lastJson(
    migrationCommand(state, ownerUrl, "status"),
    "SYNTHETIC_CI_DATABASE_RELEASE_STATUS_INVALID",
  );
  if (
    status.event !== "status" ||
    status.appliedMigrations !== count ||
    status.lastMigration !== lastMigration
  ) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_STATUS_INVALID");
  }
  const fingerprints = objectValue(
    status.targetFingerprints,
    "SYNTHETIC_CI_DATABASE_RELEASE_STATUS_INVALID",
  );
  return requiredFingerprint(
    fingerprints[approvalPhase],
    "SYNTHETIC_CI_DATABASE_RELEASE_STATUS_INVALID",
  );
}

function lineageCommand(
  state: SyntheticState,
  ownerUrl: string,
  phase:
    | "status"
    | "guard-index"
    | "backfill"
    | "indexes"
    | "validate"
    | "contract",
  approvedFingerprint?: string,
): string {
  return runInDatabaseNetwork(
    state,
    "packages/db/scripts/template-twin-lineage-online.ts",
    [
      "--phase",
      phase,
      ...(phase === "backfill"
        ? ["--batch-size", "1000", "--batch-delay-ms", "0"]
        : []),
    ],
    {
      DATABASE_URL: ownerUrl,
      ...(approvedFingerprint
        ? {
            TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT:
              approvedFingerprint,
          }
        : {}),
      ...(phase === "contract"
        ? {
            TEMPLATE_TWIN_LINEAGE_CONTRACT_ACK: `note_templates_lineage_v1:${syntheticDatabase}`,
          }
        : {}),
    },
    "SYNTHETIC_CI_DATABASE_RELEASE_LINEAGE_FAILED",
  );
}

function applyLineageProtocol(state: SyntheticState, ownerUrl: string): void {
  const readStatus = () =>
    lastJson(
      lineageCommand(state, ownerUrl, "status"),
      "SYNTHETIC_CI_DATABASE_RELEASE_LINEAGE_STATUS_INVALID",
    );
  const fingerprint = (
    status: Record<string, unknown>,
    phase: "guard-index" | "backfill" | "indexes" | "validate" | "contract",
  ) => {
    const fingerprints = objectValue(
      status.targetFingerprints,
      "SYNTHETIC_CI_DATABASE_RELEASE_LINEAGE_STATUS_INVALID",
    );
    return requiredFingerprint(
      fingerprints[phase],
      "SYNTHETIC_CI_DATABASE_RELEASE_LINEAGE_STATUS_INVALID",
    );
  };

  let status = readStatus();
  if (
    status.operationKey !== "note_templates_lineage_v1" ||
    status.phase !== "EXPANDED" ||
    status.readOnly !== true ||
    status.presentIndexesExact !== true ||
    status.validationConstraintExact !== true ||
    status.transitionContractExact !== true
  ) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_LINEAGE_STATUS_INVALID");
  }

  lineageCommand(
    state,
    ownerUrl,
    "guard-index",
    fingerprint(status, "guard-index"),
  );
  status = readStatus();
  lineageCommand(state, ownerUrl, "backfill", fingerprint(status, "backfill"));
  status = readStatus();
  const noOp = exactJsonLines(
    lineageCommand(
      state,
      ownerUrl,
      "backfill",
      fingerprint(status, "backfill"),
    ),
  ).find((record) => record.event === "batch");
  if (
    !noOp ||
    noOp.batchRows !== 0 ||
    noOp.complete !== true ||
    noOp.cursorRestarted !== false
  ) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_LINEAGE_RESUME_INVALID");
  }
  status = readStatus();
  lineageCommand(state, ownerUrl, "indexes", fingerprint(status, "indexes"));
  status = readStatus();
  lineageCommand(state, ownerUrl, "validate", fingerprint(status, "validate"));
  status = readStatus();
  lineageCommand(state, ownerUrl, "contract", fingerprint(status, "contract"));

  const finalStatus = readStatus();
  const partial = objectValue(
    finalStatus.partialIndex,
    "SYNTHETIC_CI_DATABASE_RELEASE_LINEAGE_STATUS_INVALID",
  );
  const finalIndex = objectValue(
    finalStatus.finalIndex,
    "SYNTHETIC_CI_DATABASE_RELEASE_LINEAGE_STATUS_INVALID",
  );
  const kindIndex = objectValue(
    finalStatus.templateKindIndex,
    "SYNTHETIC_CI_DATABASE_RELEASE_LINEAGE_STATUS_INVALID",
  );
  const constraint = objectValue(
    finalStatus.validationConstraint,
    "SYNTHETIC_CI_DATABASE_RELEASE_LINEAGE_STATUS_INVALID",
  );
  if (
    finalStatus.phase !== "CONTRACTED" ||
    finalStatus.nullRows !== 0 ||
    finalStatus.duplicateLineageVersions !== 0 ||
    partial.exists !== false ||
    finalIndex.exists !== true ||
    finalIndex.valid !== true ||
    finalIndex.ready !== true ||
    kindIndex.exists !== true ||
    kindIndex.valid !== true ||
    kindIndex.ready !== true ||
    constraint.exists !== true ||
    constraint.validated !== true ||
    finalStatus.presentIndexesExact !== true ||
    finalStatus.validationConstraintExact !== true ||
    finalStatus.columnNotNull !== true ||
    finalStatus.transitionTriggerPresent !== false ||
    finalStatus.transitionContractExact !== true
  ) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_LINEAGE_STATUS_INVALID");
  }
}

function authCommand(
  state: SyntheticState,
  ownerUrl: string,
  phase: "status" | "all",
  approvedFingerprint?: string,
): string {
  return runInDatabaseNetwork(
    state,
    "packages/db/scripts/auth-token-linearization-online.ts",
    [
      "--phase",
      phase,
      ...(phase === "all"
        ? ["--batch-size", "100", "--batch-delay-ms", "0"]
        : []),
    ],
    {
      AUTH_TOKEN_LINEARIZATION_DATABASE_URL: ownerUrl,
      ...(approvedFingerprint
        ? {
            AUTH_TOKEN_LINEARIZATION_APPROVED_TARGET_FINGERPRINT:
              approvedFingerprint,
          }
        : {}),
    },
    "SYNTHETIC_CI_DATABASE_RELEASE_AUTH_FAILED",
  );
}

function applyAuthProtocol(state: SyntheticState, ownerUrl: string): void {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const status = lastJson(
      authCommand(state, ownerUrl, "status"),
      "SYNTHETIC_CI_DATABASE_RELEASE_AUTH_STATUS_INVALID",
    );
    const fingerprints = objectValue(
      status.targetFingerprints,
      "SYNTHETIC_CI_DATABASE_RELEASE_AUTH_STATUS_INVALID",
    );
    const fingerprint = requiredFingerprint(
      fingerprints.all,
      "SYNTHETIC_CI_DATABASE_RELEASE_AUTH_STATUS_INVALID",
    );
    authCommand(state, ownerUrl, "all", fingerprint);
  }
  const finalStatus = lastJson(
    authCommand(state, ownerUrl, "status"),
    "SYNTHETIC_CI_DATABASE_RELEASE_AUTH_STATUS_INVALID",
  );
  if (
    finalStatus.readOnly !== true ||
    finalStatus.duplicateGroups !== 0 ||
    finalStatus.indexExists !== true ||
    finalStatus.indexValid !== true ||
    finalStatus.indexReady !== true ||
    finalStatus.indexExact !== true ||
    finalStatus.transitionTriggerEnabled !== false ||
    finalStatus.transitionTriggerState !== "absent" ||
    finalStatus.complete !== true
  ) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_AUTH_STATUS_INVALID");
  }
}

function provisionReleaseSecurity(state: SyntheticState, secret: string): void {
  const systemIdentifier = command(
    "docker",
    [
      "exec",
      state.containerName,
      "psql",
      "-X",
      "--no-psqlrc",
      "--quiet",
      "--tuples-only",
      "--no-align",
      "--username",
      databaseOwner,
      "--dbname",
      syntheticDatabase,
      "--command",
      "SELECT system_identifier FROM pg_control_system()",
    ],
    "SYNTHETIC_CI_DATABASE_RELEASE_SYSTEM_IDENTIFIER_FAILED",
    { environment: dockerEnvironment() },
  );
  if (!/^[0-9]+$/u.test(systemIdentifier)) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_SYSTEM_IDENTIFIER_INVALID");
  }
  command(
    "docker",
    [
      "exec",
      "-i",
      "--env",
      "DB_RELEASE_SECURITY_PASSWORD",
      "--env",
      "POSTGRES_USER",
      "--env",
      "POSTGRES_DB",
      "--env",
      "DB_EXPECTED_SYSTEM_IDENTIFIER",
      state.containerName,
      "/bin/sh",
      "/opt/quillmd/provision-template-twin-release-security.sh",
    ],
    "SYNTHETIC_CI_DATABASE_RELEASE_SECURITY_PROVISION_FAILED",
    {
      environment: dockerEnvironment({
        DB_RELEASE_SECURITY_PASSWORD: secret,
        POSTGRES_USER: databaseOwner,
        POSTGRES_DB: syntheticDatabase,
        DB_EXPECTED_SYSTEM_IDENTIFIER: systemIdentifier,
      }),
    },
  );
}

function proveExactPrincipals(
  state: SyntheticState,
  secrets: Record<string, string>,
): void {
  const profiles = [
    ["runtime", "meddoc_runtime", secrets.runtime],
    ["release-control", "meddoc_release_control", secrets.releaseControl],
    ["release-security", "meddoc_release_security", secrets.releaseSecurity],
    ["audit-dispatcher", "meddoc_audit_dispatcher", secrets.auditDispatcher],
    [
      "auth-email-dispatcher",
      "meddoc_auth_email_dispatcher",
      secrets.authEmailDispatcher,
    ],
    ["backup", "meddoc_backup", secrets.backup],
  ] as const;
  for (const [profile, login, secret] of profiles) {
    const output = runInDatabaseNetwork(
      state,
      "packages/db/scripts/exact-database-principal-preflight.ts",
      [],
      {
        EXACT_DATABASE_PRINCIPAL_DATABASE_URL: internalDatabaseUrl(
          login,
          secret,
        ),
        EXACT_DATABASE_PRINCIPAL_PROFILE: profile,
        PRISMA_STATEMENT_TIMEOUT_MS: "30000",
      },
      "SYNTHETIC_CI_DATABASE_RELEASE_PRINCIPAL_PREFLIGHT_FAILED",
    );
    if (output !== "EXACT_DATABASE_PRINCIPAL_PREFLIGHT_PASS") {
      fail("SYNTHETIC_CI_DATABASE_RELEASE_PRINCIPAL_PREFLIGHT_FAILED");
    }
  }
}

function waitForPostgres(state: SyntheticState): void {
  for (let attempt = 0; attempt < 180; attempt += 1) {
    const status = command(
      "docker",
      [
        "container",
        "inspect",
        "--format",
        "{{.State.Health.Status}}",
        state.containerName,
      ],
      "SYNTHETIC_CI_DATABASE_RELEASE_HEALTH_FAILED",
      { environment: dockerEnvironment(), tolerateFailure: true },
    );
    if (status === "healthy") return;
    const sleeper = spawnSync("sleep", ["1"], { stdio: "ignore" });
    if (sleeper.status !== 0) {
      fail("SYNTHETIC_CI_DATABASE_RELEASE_HEALTH_FAILED");
    }
  }
  fail("SYNTHETIC_CI_DATABASE_RELEASE_HEALTH_TIMEOUT");
}

function appendGithubEnvironment(
  path: string,
  state: SyntheticState,
  runtimeSecret: string,
  ownerSecret: string,
): void {
  const published = command(
    "docker",
    ["port", state.containerName, "5432/tcp"],
    "SYNTHETIC_CI_DATABASE_RELEASE_PORT_FAILED",
    { environment: dockerEnvironment() },
  );
  const match = /^127\.0\.0\.1:([1-9][0-9]{0,4})$/u.exec(published);
  const port = Number(match?.[1]);
  if (!match || !Number.isSafeInteger(port) || port > 65_535) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_PORT_INVALID");
  }
  const runtimeUrl = externalDatabaseUrl("meddoc_runtime", runtimeSecret, port);
  const passwordFile = join(state.temporaryDirectory, "owner.pgpass");
  writeFileSync(
    passwordFile,
    `127.0.0.1:${port}:${syntheticDatabase}:${databaseOwner}:${ownerSecret}\n`,
    { encoding: "utf8", mode: 0o600 },
  );
  chmodSync(passwordFile, 0o600);
  const lines = [
    `DATABASE_URL=${runtimeUrl}`,
    `PGPASSFILE=${passwordFile}`,
    `PSQL_BIN=psql --no-password --host 127.0.0.1 --port ${port} --username ${databaseOwner} --dbname ${syntheticDatabase}`,
    "QUILLMD_SERVICE_ROLE=physician-app",
    "QUILLMD_DATABASE_PRINCIPAL_PROFILE=synthetic-disposable-qa-v1",
    "QUILLMD_SYNTHETIC_CI_DATABASE_PROVISIONED=true",
  ];
  for (const line of lines) {
    if (/\r|\n/u.test(line)) {
      fail("SYNTHETIC_CI_DATABASE_RELEASE_ENVIRONMENT_INVALID");
    }
  }
  writeFileSync(path, `${lines.join("\n")}\n`, {
    encoding: "utf8",
    flag: "a",
  });
}

function provision(
  boundary: ReturnType<typeof assertSyntheticCiBoundary>,
): void {
  if (existsSync(boundary.statePath)) {
    fail("SYNTHETIC_CI_DATABASE_RELEASE_STATE_EXISTS");
  }
  const token = randomBytes(12).toString("hex");
  const state: SyntheticState = {
    version: "quillmd-synthetic-ci-database-state-v1",
    token,
    containerName: `${containerPrefix}${token}`,
    volumeName: `${volumePrefix}${token}`,
    imageTag: `${imagePrefix}${token}`,
    temporaryDirectory: join(
      boundary.runnerTemp,
      `quillmd-synthetic-ci-${token}`,
    ),
    ready: false,
  };
  validateState(state, boundary.runnerTemp);
  mkdirSync(state.temporaryDirectory, { mode: 0o700 });
  chmodSync(state.temporaryDirectory, 0o700);
  writeState(boundary.statePath, state);

  // This helper cannot return until every distinct raw credential is masked.
  // Registering the raw components also protects URLs and pgpass records that
  // embed them later in the release sequence.
  const secrets = generateMaskedSyntheticDatabaseSecrets();
  const backupPath = join(state.temporaryDirectory, "backup-password");
  writeFileSync(backupPath, secrets.backup, { mode: 0o444 });
  chmodSync(backupPath, 0o444);
  const expectedLabel = `${resourceLabelVersion}:${token}`;
  let provisionStage = "IMAGE_CONTRACT";

  try {
    const dockerfile = readFileSync(
      join(repositoryRoot, "infra/postgres/Dockerfile"),
      "utf8",
    );
    const entrypoint = readFileSync(
      join(repositoryRoot, "infra/postgres/quillmd-postgres-entrypoint.sh"),
      "utf8",
    );
    if (
      !dockerfile.includes(
        `quillmd.hba_contract_sha256=${startupContractSha256}`,
      ) ||
      !entrypoint.includes(`contract_sha256=${startupContractSha256}`)
    ) {
      fail("SYNTHETIC_CI_DATABASE_RELEASE_IMAGE_CONTRACT_INVALID");
    }
    provisionStage = "IMAGE_BUILD";
    command(
      "docker",
      [
        "build",
        "--file",
        "infra/postgres/Dockerfile",
        "--label",
        `${resourceLabel}=${expectedLabel}`,
        "--tag",
        state.imageTag,
        "infra/postgres",
      ],
      "SYNTHETIC_CI_DATABASE_RELEASE_IMAGE_BUILD_FAILED",
      {
        environment: dockerEnvironment(),
        inheritOutput: true,
        timeoutMs: 20 * 60_000,
      },
    );
    provisionStage = "VOLUME_CREATE";
    command(
      "docker",
      [
        "volume",
        "create",
        "--label",
        `${resourceLabel}=${expectedLabel}`,
        state.volumeName,
      ],
      "SYNTHETIC_CI_DATABASE_RELEASE_VOLUME_CREATE_FAILED",
      { environment: dockerEnvironment() },
    );
    provisionStage = "CONTAINER_START";
    command(
      "docker",
      [
        "run",
        "--detach",
        "--name",
        state.containerName,
        "--label",
        `${resourceLabel}=${expectedLabel}`,
        "--user",
        "999:999",
        "--cap-drop",
        "ALL",
        "--read-only",
        "--memory",
        "512m",
        "--cpus",
        "1.0",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777",
        "--tmpfs",
        "/var/run/postgresql:rw,noexec,nosuid,nodev,size=16m,uid=999,gid=999,mode=3777",
        "--publish",
        "127.0.0.1::5432",
        "--volume",
        `${state.volumeName}:/var/lib/postgresql/data`,
        "--mount",
        `type=bind,src=${join(repositoryRoot, "infra/postgres/init-template-twin-roles.sh")},dst=/docker-entrypoint-initdb.d/20-quillmd-exact-principals.sh,readonly`,
        "--mount",
        `type=bind,src=${join(repositoryRoot, "infra/postgres/provision-template-twin-release-security.sh")},dst=/opt/quillmd/provision-template-twin-release-security.sh,readonly`,
        "--mount",
        `type=bind,src=${backupPath},dst=/run/secrets/synthetic_postgres_backup_password,readonly`,
        "--env",
        "POSTGRES_DB",
        "--env",
        "POSTGRES_USER",
        "--env",
        "POSTGRES_PASSWORD",
        "--env",
        "POSTGRES_INITDB_ARGS",
        "--env",
        "PGDATA",
        "--env",
        "DB_RUNTIME_PASSWORD",
        "--env",
        "DB_RELEASE_CONTROL_PASSWORD",
        "--env",
        "DB_AUDIT_DISPATCHER_PASSWORD",
        "--env",
        "DB_AUTH_EMAIL_DISPATCHER_PASSWORD",
        "--env",
        "DB_BACKUP_PASSWORD_FILE",
        "--health-cmd",
        "/bin/sh /opt/quillmd/verify-quillmd-host-auth.sh",
        "--health-interval",
        "2s",
        "--health-timeout",
        "5s",
        "--health-retries",
        "90",
        state.imageTag,
      ],
      "SYNTHETIC_CI_DATABASE_RELEASE_CONTAINER_START_FAILED",
      {
        environment: dockerEnvironment({
          POSTGRES_DB: syntheticDatabase,
          POSTGRES_USER: databaseOwner,
          POSTGRES_PASSWORD: secrets.owner,
          POSTGRES_INITDB_ARGS: "--auth-host=scram-sha-256 --auth-local=trust",
          PGDATA: "/var/lib/postgresql/data/pgdata",
          DB_RUNTIME_PASSWORD: secrets.runtime,
          DB_RELEASE_CONTROL_PASSWORD: secrets.releaseControl,
          DB_AUDIT_DISPATCHER_PASSWORD: secrets.auditDispatcher,
          DB_AUTH_EMAIL_DISPATCHER_PASSWORD: secrets.authEmailDispatcher,
          DB_BACKUP_PASSWORD_FILE:
            "/run/secrets/synthetic_postgres_backup_password",
        }),
      },
    );
    provisionStage = "DATABASE_READY";
    waitForPostgres(state);

    const ownerUrl = internalDatabaseUrl(databaseOwner, secrets.owner);
    provisionStage = "LINEAGE_EXPAND_STATUS";
    const lineageFingerprint = migrationStatus(
      state,
      ownerUrl,
      0,
      null,
      "lineage-expand",
    );
    provisionStage = "LINEAGE_EXPAND";
    migrationCommand(state, ownerUrl, "lineage-expand", lineageFingerprint);
    provisionStage = "LINEAGE_ONLINE";
    applyLineageProtocol(state, ownerUrl);

    provisionStage = "AUTH_EXPAND_STATUS";
    const authFingerprint = migrationStatus(
      state,
      ownerUrl,
      68,
      "20260715162000_template_twin_docx_v1",
      "auth-expand",
    );
    provisionStage = "AUTH_EXPAND";
    migrationCommand(state, ownerUrl, "auth-expand", authFingerprint);
    provisionStage = "AUTH_ONLINE";
    applyAuthProtocol(state, ownerUrl);

    provisionStage = "PRE_V9_STATUS";
    const preV9Fingerprint = migrationStatus(
      state,
      ownerUrl,
      93,
      "20260720150000_auth_token_linearization_v5",
      "pre-v9",
    );
    provisionStage = "PRE_V9";
    migrationCommand(state, ownerUrl, "pre-v9", preV9Fingerprint);
    provisionStage = "RELEASE_SECURITY";
    provisionReleaseSecurity(state, secrets.releaseSecurity);

    provisionStage = "V9_STATUS";
    const v9Fingerprint = migrationStatus(
      state,
      ownerUrl,
      96,
      "20260720200000_mfa_credential_lifecycle_audit_v8",
      "v9",
    );
    provisionStage = "V9";
    migrationCommand(state, ownerUrl, "v9", v9Fingerprint);
    provisionStage = "FINAL_STATUS";
    migrationStatus(
      state,
      ownerUrl,
      97,
      "20260720213000_exact_database_principal_closure_v9",
      "v9",
    );
    provisionStage = "EXACT_PRINCIPALS";
    proveExactPrincipals(state, secrets);

    provisionStage = "PUBLISH";
    state.ready = true;
    writeState(boundary.statePath, state);
    appendGithubEnvironment(
      boundary.githubEnvironment,
      state,
      secrets.runtime,
      secrets.owner,
    );
    process.stdout.write("SYNTHETIC_CI_DATABASE_RELEASE_PROVISION_PASS\n");
  } catch (error) {
    try {
      cleanupState(state, boundary.runnerTemp, boundary.statePath);
    } catch {
      fail("SYNTHETIC_CI_DATABASE_RELEASE_FAILURE_CLEANUP_FAILED");
    }
    if (
      error instanceof Error &&
      /^SYNTHETIC_CI_DATABASE_RELEASE_[A-Z0-9_]{2,120}$/u.test(error.message)
    ) {
      throw error;
    }
    fail(`SYNTHETIC_CI_DATABASE_RELEASE_${provisionStage}_FAILED`);
  }
}

export function cleanup(
  boundary: ReturnType<typeof assertSyntheticCiBoundary>,
): void {
  if (!existsSync(boundary.statePath)) {
    process.stdout.write("SYNTHETIC_CI_DATABASE_RELEASE_CLEANUP_NOOP\n");
    return;
  }
  const state = validateState(
    JSON.parse(readFileSync(boundary.statePath, "utf8")) as unknown,
    boundary.runnerTemp,
  );
  cleanupState(state, boundary.runnerTemp, boundary.statePath);
  process.stdout.write("SYNTHETIC_CI_DATABASE_RELEASE_CLEANUP_PASS\n");
}

function main(): void {
  let stage = "STARTUP";
  try {
    stage = "ARGUMENTS";
    const phase = parsePhase(process.argv.slice(2));
    stage = "BOUNDARY";
    const boundary = assertSyntheticCiBoundary(phase);
    stage = phase === "provision" ? "PROVISION" : "CLEANUP";
    if (phase === "provision") provision(boundary);
    else cleanup(boundary);
  } catch (error) {
    const safe =
      error instanceof Error &&
      /^SYNTHETIC_CI_DATABASE_RELEASE_[A-Z0-9_]{2,120}$/u.test(error.message)
        ? error.message
        : `SYNTHETIC_CI_DATABASE_RELEASE_${stage}_FAILED`;
    process.stderr.write(`${safe}\n`);
    process.exitCode = 1;
  }
}

if (process.env.VITEST !== "true") main();
