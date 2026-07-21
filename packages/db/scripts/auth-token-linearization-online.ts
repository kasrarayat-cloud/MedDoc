#!/usr/bin/env tsx

// Bounded online operator for the auth-token partial uniqueness invariant.
// It never prints a connection string, token, user identity, or credential.

import { createHash } from "node:crypto";
import { performance } from "node:perf_hooks";

import { Pool, type PoolClient } from "pg";

import { assertNonProdDatabase, describeDbTarget } from "../src/db-guard";
import {
  AUTH_TOKEN_LINEARIZATION_PROOF_CONTRACT_VERSION,
  buildAuthTokenUniqueIndex,
  readAuthTokenLinearizationStatusSnapshot,
  reconcileAuthTokenDuplicateBatch,
  type AuthTokenLinearizationStatus,
} from "../src/auth-token-linearization-online";
import { acquireAuthTokenOperatorSessionLockOnClient } from "../src/auth-token-linearization-session-lock";
import {
  buildDatabaseConnectionString,
  DATABASE_SEARCH_PATH,
} from "../src/database-connection-string";

export type AuthTokenOperatorPhase = "status" | "reconcile" | "index" | "all";
type MutatingPhase = Exclude<AuthTokenOperatorPhase, "status">;

interface Options {
  phase: AuthTokenOperatorPhase;
  batchSize: number;
  batchDelayMs: number;
  maxBatches: number | null;
}

const AUTH_TOKEN_OPERATOR_APPLICATION_NAME =
  "quillmd_auth_token_linearization_online_v1";
const AUTH_TOKEN_OPERATOR_LOCK_TIMEOUT_MS = 2_000;
const AUTH_TOKEN_OPERATOR_SHORT_STATEMENT_TIMEOUT_MS = 30_000;
const AUTH_TOKEN_OPERATOR_INDEX_STATEMENT_TIMEOUT_MS = 15 * 60_000;
const AUTH_TOKEN_OPERATOR_TARGET_FINGERPRINT_VERSION =
  "quillmd-auth-token-operator-target-v2";
const AUTH_TOKEN_OPERATOR_PRINCIPAL = "meddoc";

interface ConfiguredTarget {
  host: string;
  port: number;
  database: string;
  login: string;
}

export interface AuthTokenOperatorTarget extends ConfiguredTarget {
  serverAddress: string;
  serverPort: number;
  postgresMajor: number;
  systemIdentifier: string;
  tlsIdentity: string;
  databaseOid: string;
  databaseOwner: string;
  databaseOwnerOid: string;
  principalOid: string;
  principalCanLogin: boolean;
  principalSuperuser: boolean;
  inRecovery: boolean;
}

interface SessionTargetRow {
  sessionRole: string;
  currentRole: string;
  database: string;
  serverAddress: string | null;
  serverPort: number | null;
  serverVersionNumber: number;
  systemIdentifier: string;
  searchPath: string;
  statementTimeoutMs: number;
  lockTimeoutMs: number;
  applicationName: string;
  transactionReadOnly: string;
  ssl: boolean;
  databaseOid: string;
  databaseOwner: string;
  databaseOwnerOid: string;
  principalOid: string;
  principalCanLogin: boolean;
  principalSuperuser: boolean;
  inRecovery: boolean;
}

function integer(value: string, flag: string, minimum: number): number {
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < minimum) {
    throw new Error(`${flag} requires an integer >= ${minimum}`);
  }
  return parsed;
}

export function parseAuthTokenOperatorArgs(args: string[]): Options {
  let phase: AuthTokenOperatorPhase | null = null;
  let batchSize = 100;
  let batchDelayMs = 100;
  let maxBatches: number | null = null;
  const seen = new Set<string>();
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index]!;
    if (seen.has(arg)) throw new Error(`Duplicate argument: ${arg}`);
    seen.add(arg);
    if (arg === "--phase") {
      const value = args[++index] as AuthTokenOperatorPhase | undefined;
      if (!value || !["status", "reconcile", "index", "all"].includes(value)) {
        throw new Error("--phase must be status, reconcile, index, or all");
      }
      phase = value;
    } else if (arg === "--batch-size") {
      batchSize = integer(args[++index] ?? "", arg, 1);
    } else if (arg === "--batch-delay-ms") {
      batchDelayMs = integer(args[++index] ?? "", arg, 0);
    } else if (arg === "--max-batches") {
      maxBatches = integer(args[++index] ?? "", arg, 1);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  if (!phase) throw new Error("--phase is required");
  return { phase, batchSize, batchDelayMs, maxBatches };
}

function authorized(databaseUrl: string, phase: AuthTokenOperatorPhase): void {
  if (phase === "status") return;
  try {
    assertNonProdDatabase(databaseUrl);
  } catch (nonProductionError) {
    const target = describeDbTarget(databaseUrl);
    const allow =
      process.env.AUTH_TOKEN_LINEARIZATION_ALLOW_PRODUCTION === "true";
    const changeId =
      process.env.AUTH_TOKEN_LINEARIZATION_PRODUCTION_CHANGE_ID?.trim();
    const acknowledgement =
      process.env.AUTH_TOKEN_LINEARIZATION_PRODUCTION_ACK?.trim();
    if (
      !allow ||
      !changeId ||
      acknowledgement !== `${target.database}:${phase}`
    ) {
      throw nonProductionError;
    }
  }
}

function statementTimeoutMs(phase: AuthTokenOperatorPhase): number {
  return phase === "index" || phase === "all"
    ? AUTH_TOKEN_OPERATOR_INDEX_STATEMENT_TIMEOUT_MS
    : AUTH_TOKEN_OPERATOR_SHORT_STATEMENT_TIMEOUT_MS;
}

export function buildAuthTokenOperatorConnectionString(
  databaseUrl: string,
  phase: AuthTokenOperatorPhase,
): string {
  const connectionString = buildDatabaseConnectionString(
    databaseUrl,
    statementTimeoutMs(phase),
    {
      lockTimeoutMs: AUTH_TOKEN_OPERATOR_LOCK_TIMEOUT_MS,
      applicationName: AUTH_TOKEN_OPERATOR_APPLICATION_NAME,
      ...(phase === "status" ? { defaultTransactionReadOnly: true } : {}),
    },
  );
  if (
    decodeURIComponent(new URL(connectionString).username) !==
    AUTH_TOKEN_OPERATOR_PRINCIPAL
  ) {
    throw new Error("AUTH_TOKEN_LINEARIZATION_TARGET_PRINCIPAL_MISMATCH");
  }
  return connectionString;
}

function configuredTarget(connectionString: string): ConfiguredTarget {
  const url = new URL(connectionString);
  const target = {
    host: url.hostname.toLowerCase(),
    port: url.port ? Number(url.port) : 5_432,
    database: decodeURIComponent(url.pathname.slice(1)),
    login: decodeURIComponent(url.username),
  };
  if (target.login !== AUTH_TOKEN_OPERATOR_PRINCIPAL) {
    throw new Error("AUTH_TOKEN_LINEARIZATION_TARGET_PRINCIPAL_MISMATCH");
  }
  if (
    !target.host ||
    !target.database ||
    !Number.isSafeInteger(target.port) ||
    target.port < 1 ||
    target.port > 65_535
  ) {
    throw new Error("AUTH_TOKEN_LINEARIZATION_TARGET_INVALID");
  }
  return target;
}

function normalizeTlsFingerprint(value: string): string {
  const normalized = value.replaceAll(":", "").toLowerCase();
  if (!/^[a-f0-9]{64}$/u.test(normalized)) {
    throw new Error("AUTH_TOKEN_LINEARIZATION_SESSION_TARGET_MISMATCH");
  }
  return normalized;
}

function actualTlsIdentity(client: PoolClient, ssl: boolean): string {
  const stream = (
    client as unknown as {
      connection?: {
        stream?: {
          encrypted?: boolean;
          authorized?: boolean;
          getPeerCertificate?: () => { fingerprint256?: string };
        };
      };
    }
  ).connection?.stream;
  if (!ssl) {
    if (stream?.encrypted === true) {
      throw new Error("AUTH_TOKEN_LINEARIZATION_SESSION_TARGET_MISMATCH");
    }
    return "plaintext";
  }
  if (
    stream?.encrypted !== true ||
    typeof stream.getPeerCertificate !== "function"
  ) {
    throw new Error("AUTH_TOKEN_LINEARIZATION_SESSION_TARGET_MISMATCH");
  }
  const fingerprint = stream.getPeerCertificate().fingerprint256;
  if (!fingerprint) {
    throw new Error("AUTH_TOKEN_LINEARIZATION_SESSION_TARGET_MISMATCH");
  }
  const trust = stream.authorized === true ? "authorized" : "unverified";
  return `x509-${trust}-sha256:${normalizeTlsFingerprint(fingerprint)}`;
}

export function authTokenOperatorTargetFingerprint(
  target: AuthTokenOperatorTarget,
  phase: MutatingPhase,
  protocolEpoch: string,
): string {
  const canonical = JSON.stringify([
    AUTH_TOKEN_OPERATOR_TARGET_FINGERPRINT_VERSION,
    ["host", target.host],
    ["port", target.port],
    ["database", target.database],
    ["login", target.login],
    ["tlsIdentity", target.tlsIdentity],
    ["phase", phase],
    ["serverAddress", target.serverAddress],
    ["serverPort", target.serverPort],
    ["postgresMajor", target.postgresMajor],
    ["systemIdentifier", target.systemIdentifier],
    ["databaseOid", target.databaseOid],
    ["databaseOwner", target.databaseOwner],
    ["databaseOwnerOid", target.databaseOwnerOid],
    ["principalOid", target.principalOid],
    ["principalCanLogin", target.principalCanLogin],
    ["principalSuperuser", target.principalSuperuser],
    ["inRecovery", target.inRecovery],
    ["proofContractVersion", AUTH_TOKEN_LINEARIZATION_PROOF_CONTRACT_VERSION],
    ["protocolEpoch", protocolEpoch],
  ]);
  return createHash("sha256").update(canonical, "utf8").digest("hex");
}

export function authTokenOperatorProtocolEpoch(
  status: AuthTokenLinearizationStatus,
): string {
  return createHash("sha256")
    .update(
      JSON.stringify([
        "quillmd-auth-token-linearization-protocol-epoch-v1",
        AUTH_TOKEN_LINEARIZATION_PROOF_CONTRACT_VERSION,
        status.duplicateGroups,
        status.indexExists,
        status.indexValid,
        status.indexReady,
        status.indexExact,
        status.transitionTriggerEnabled,
        status.transitionTriggerState,
        status.complete,
      ]),
      "utf8",
    )
    .digest("hex");
}

export function authTokenOperatorApprovalFingerprint(
  target: AuthTokenOperatorTarget,
  status: AuthTokenLinearizationStatus,
  phase: MutatingPhase,
): string {
  return authTokenOperatorTargetFingerprint(
    target,
    phase,
    authTokenOperatorProtocolEpoch(status),
  );
}

export function assertApprovedAuthTokenOperatorTarget(
  target: AuthTokenOperatorTarget,
  status: AuthTokenLinearizationStatus,
  phase: MutatingPhase,
  approvedFingerprint: string | undefined,
): void {
  if (
    target.login !== AUTH_TOKEN_OPERATOR_PRINCIPAL ||
    target.databaseOwner !== AUTH_TOKEN_OPERATOR_PRINCIPAL ||
    target.databaseOwnerOid !== target.principalOid ||
    !/^[0-9]+$/u.test(target.databaseOid) ||
    !/^[0-9]+$/u.test(target.principalOid) ||
    target.principalCanLogin !== true ||
    target.principalSuperuser !== true
  ) {
    throw new Error("AUTH_TOKEN_LINEARIZATION_TARGET_PRINCIPAL_MISMATCH");
  }
  if (target.inRecovery) {
    throw new Error("AUTH_TOKEN_LINEARIZATION_TARGET_IN_RECOVERY");
  }
  if (!approvedFingerprint || !/^[a-f0-9]{64}$/u.test(approvedFingerprint)) {
    throw new Error("AUTH_TOKEN_LINEARIZATION_TARGET_APPROVAL_REQUIRED");
  }
  if (
    approvedFingerprint !==
    authTokenOperatorApprovalFingerprint(target, status, phase)
  ) {
    throw new Error("AUTH_TOKEN_LINEARIZATION_TARGET_APPROVAL_MISMATCH");
  }
}

export async function preflightAuthTokenOperatorTarget(
  client: PoolClient,
  expected: ConfiguredTarget,
  phase: AuthTokenOperatorPhase,
): Promise<AuthTokenOperatorTarget> {
  const result = await client.query<SessionTargetRow>(`
    SELECT
      session_user AS "sessionRole",
      current_user AS "currentRole",
      current_database() AS "database",
      pg_catalog.inet_server_addr()::TEXT AS "serverAddress",
      pg_catalog.inet_server_port() AS "serverPort",
      current_setting('server_version_num')::INTEGER AS "serverVersionNumber",
      (SELECT control.system_identifier::TEXT
         FROM pg_catalog.pg_control_system() control) AS "systemIdentifier",
      current_setting('search_path') AS "searchPath",
      (SELECT setting::INTEGER FROM pg_catalog.pg_settings
        WHERE name = 'statement_timeout') AS "statementTimeoutMs",
      (SELECT setting::INTEGER FROM pg_catalog.pg_settings
        WHERE name = 'lock_timeout') AS "lockTimeoutMs",
      current_setting('application_name') AS "applicationName",
      current_setting('transaction_read_only') AS "transactionReadOnly",
      COALESCE((SELECT ssl FROM pg_catalog.pg_stat_ssl
        WHERE pid = pg_catalog.pg_backend_pid()), FALSE) AS "ssl",
      database_state.oid::TEXT AS "databaseOid",
      database_owner.rolname::TEXT AS "databaseOwner",
      database_owner.oid::TEXT AS "databaseOwnerOid",
      principal.oid::TEXT AS "principalOid",
      principal.rolcanlogin AS "principalCanLogin",
      principal.rolsuper AS "principalSuperuser",
      pg_catalog.pg_is_in_recovery() AS "inRecovery"
    FROM pg_catalog.pg_database database_state
    JOIN pg_catalog.pg_roles database_owner
      ON database_owner.oid = database_state.datdba
    JOIN pg_catalog.pg_roles principal
      ON principal.rolname = session_user
    WHERE database_state.datname = current_database()
  `);
  const row = result.rows[0];
  const observable = client as unknown as {
    user?: string;
    database?: string;
    host?: string;
    port?: number;
  };
  if (
    result.rows.length !== 1 ||
    !row ||
    observable.host?.toLowerCase() !== expected.host ||
    observable.port !== expected.port ||
    observable.database !== expected.database ||
    observable.user !== expected.login ||
    expected.login !== AUTH_TOKEN_OPERATOR_PRINCIPAL ||
    row.sessionRole !== AUTH_TOKEN_OPERATOR_PRINCIPAL ||
    row.currentRole !== AUTH_TOKEN_OPERATOR_PRINCIPAL ||
    row.database !== expected.database ||
    !/^[0-9]+$/u.test(row.databaseOid) ||
    row.databaseOwner !== AUTH_TOKEN_OPERATOR_PRINCIPAL ||
    !/^[0-9]+$/u.test(row.databaseOwnerOid) ||
    !/^[0-9]+$/u.test(row.principalOid) ||
    row.databaseOwnerOid !== row.principalOid ||
    row.principalCanLogin !== true ||
    row.principalSuperuser !== true ||
    !row.serverAddress ||
    !Number.isSafeInteger(row.serverPort) ||
    row.serverPort! < 1 ||
    row.serverPort! > 65_535 ||
    Math.trunc(row.serverVersionNumber / 10_000) !== 16 ||
    !/^[0-9]+$/u.test(row.systemIdentifier) ||
    row.searchPath !== DATABASE_SEARCH_PATH ||
    row.statementTimeoutMs !== statementTimeoutMs(phase) ||
    row.lockTimeoutMs !== AUTH_TOKEN_OPERATOR_LOCK_TIMEOUT_MS ||
    row.applicationName !== AUTH_TOKEN_OPERATOR_APPLICATION_NAME ||
    row.transactionReadOnly !== (phase === "status" ? "on" : "off") ||
    typeof row.inRecovery !== "boolean"
  ) {
    throw new Error("AUTH_TOKEN_LINEARIZATION_SESSION_TARGET_MISMATCH");
  }
  return {
    ...expected,
    serverAddress: row.serverAddress.toLowerCase(),
    serverPort: row.serverPort,
    postgresMajor: Math.trunc(row.serverVersionNumber / 10_000),
    systemIdentifier: row.systemIdentifier,
    tlsIdentity: actualTlsIdentity(client, row.ssl),
    databaseOid: row.databaseOid,
    databaseOwner: row.databaseOwner,
    databaseOwnerOid: row.databaseOwnerOid,
    principalOid: row.principalOid,
    principalCanLogin: row.principalCanLogin,
    principalSuperuser: row.principalSuperuser,
    inRecovery: row.inRecovery,
  };
}

export function authTokenOperatorTargetFingerprints(
  target: AuthTokenOperatorTarget,
  status: AuthTokenLinearizationStatus,
): Partial<Record<MutatingPhase, string>> {
  if (target.inRecovery) return {};
  const epoch = authTokenOperatorProtocolEpoch(status);
  return Object.fromEntries(
    (["reconcile", "index", "all"] as const).map((phase) => [
      phase,
      authTokenOperatorTargetFingerprint(target, phase, epoch),
    ]),
  ) as Partial<Record<MutatingPhase, string>>;
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function printSafe(value: unknown): void {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

const SAFE_INTERNAL_ERROR_CODES = new Set([
  "AUTH_TOKEN_DUPLICATES_REMAIN",
  "AUTH_TOKEN_DUPLICATE_GROUP_COUNT_INVALID",
  "AUTH_TOKEN_INDEX_CATALOG_AMBIGUOUS",
  "AUTH_TOKEN_INDEX_DEFINITION_MISMATCH",
  "AUTH_TOKEN_INDEX_NOT_VALID",
  "AUTH_TOKEN_INVALID_INDEX_DEFINITION_MISMATCH",
  "AUTH_TOKEN_LINEARIZATION_BATCH_SIZE_INVALID",
  "AUTH_TOKEN_LINEARIZATION_INCOMPLETE",
  "AUTH_TOKEN_LINEARIZATION_LOCK_ACQUIRE_FAILED",
  "AUTH_TOKEN_LINEARIZATION_OPERATOR_BUSY",
  "AUTH_TOKEN_LINEARIZATION_SESSION_TARGET_MISMATCH",
  "AUTH_TOKEN_LINEARIZATION_TARGET_APPROVAL_MISMATCH",
  "AUTH_TOKEN_LINEARIZATION_TARGET_APPROVAL_REQUIRED",
  "AUTH_TOKEN_LINEARIZATION_TARGET_IN_RECOVERY",
  "AUTH_TOKEN_LINEARIZATION_TARGET_PRINCIPAL_MISMATCH",
  "AUTH_TOKEN_RECONCILED_KEY_COUNT_INVALID",
  "AUTH_TOKEN_RETIRED_ROW_COUNT_INVALID",
  "AUTH_TOKEN_TRANSITION_GUARD_MISMATCH",
  "AUTH_TOKEN_TRANSITION_GUARD_REQUIRED",
]);

export function safeAuthTokenOperatorErrorCode(error: unknown): string {
  return error instanceof Error && SAFE_INTERNAL_ERROR_CODES.has(error.message)
    ? error.message
    : "AUTH_TOKEN_LINEARIZATION_OPERATOR_FAILED";
}

async function run(): Promise<void> {
  let pool: Pool | null = null;
  let client: PoolClient | null = null;
  let operatorLock: Awaited<
    ReturnType<typeof acquireAuthTokenOperatorSessionLockOnClient>
  > | null = null;
  let stopping = false;
  const stop = () => {
    stopping = true;
  };
  process.once("SIGINT", stop);
  process.once("SIGTERM", stop);
  try {
    const options = parseAuthTokenOperatorArgs(process.argv.slice(2));
    const databaseUrl = process.env.AUTH_TOKEN_LINEARIZATION_DATABASE_URL;
    if (!databaseUrl) {
      throw new Error("AUTH_TOKEN_LINEARIZATION_DATABASE_URL is required");
    }
    const operatorConnectionString = buildAuthTokenOperatorConnectionString(
      databaseUrl,
      options.phase,
    );
    const expectedTarget = configuredTarget(operatorConnectionString);
    authorized(operatorConnectionString, options.phase);
    pool = new Pool({
      connectionString: operatorConnectionString,
      max: 1,
      connectionTimeoutMillis: 10_000,
    });
    client = await pool.connect();
    const liveTarget = await preflightAuthTokenOperatorTarget(
      client,
      expectedTarget,
      options.phase,
    );
    const observedStatus =
      await readAuthTokenLinearizationStatusSnapshot(client);
    if (options.phase === "status") {
      printSafe({
        event: "status",
        readOnly: true,
        targetFingerprints: authTokenOperatorTargetFingerprints(
          liveTarget,
          observedStatus,
        ),
        ...observedStatus,
      });
      return;
    }
    assertApprovedAuthTokenOperatorTarget(
      liveTarget,
      observedStatus,
      options.phase,
      process.env.AUTH_TOKEN_LINEARIZATION_APPROVED_TARGET_FINGERPRINT,
    );
    operatorLock = await acquireAuthTokenOperatorSessionLockOnClient(client);
    const lockedStatus = await readAuthTokenLinearizationStatusSnapshot(client);
    if (
      authTokenOperatorProtocolEpoch(lockedStatus) !==
      authTokenOperatorProtocolEpoch(observedStatus)
    ) {
      throw new Error("AUTH_TOKEN_LINEARIZATION_TARGET_APPROVAL_MISMATCH");
    }
    if (options.phase === "reconcile" || options.phase === "all") {
      let batches = 0;
      while (!stopping) {
        const started = performance.now();
        const result = await reconcileAuthTokenDuplicateBatch(
          client,
          options.batchSize,
        );
        if (result.duplicateKeys > 0) batches += 1;
        printSafe({
          event: "reconcile_batch",
          durationMs: Math.round((performance.now() - started) * 100) / 100,
          ...result,
        });
        if (result.complete || stopping) break;
        if (options.maxBatches !== null && batches >= options.maxBatches) {
          printSafe({ event: "paused", reason: "max_batches", batches });
          break;
        }
        if (options.batchDelayMs > 0) await sleep(options.batchDelayMs);
      }
      const status = await readAuthTokenLinearizationStatusSnapshot(client);
      if (
        options.phase === "reconcile" ||
        stopping ||
        status.duplicateGroups > 0
      ) {
        printSafe({ event: "status", ...status });
        return;
      }
    }
    await buildAuthTokenUniqueIndex(client);
    printSafe({
      event: "status",
      ...(await readAuthTokenLinearizationStatusSnapshot(client)),
    });
  } catch (error) {
    process.stderr.write(`${safeAuthTokenOperatorErrorCode(error)}\n`);
    process.exitCode = 1;
  } finally {
    let cleanupFailed = false;
    if (operatorLock) {
      try {
        await operatorLock.release();
      } catch {
        cleanupFailed = true;
      }
    }
    client?.release();
    if (pool) {
      try {
        await pool.end();
      } catch {
        cleanupFailed = true;
      }
    }
    if (cleanupFailed) {
      process.stderr.write("AUTH_TOKEN_LINEARIZATION_CLEANUP_FAILED\n");
      process.exitCode = 1;
    }
  }
}

if (process.env.VITEST !== "true") {
  void run().catch(() => {
    process.stderr.write("AUTH_TOKEN_LINEARIZATION_OPERATOR_FAILED\n");
    process.exitCode = 1;
  });
}
