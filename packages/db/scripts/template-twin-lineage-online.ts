#!/usr/bin/env tsx

// Target-bound online operator for the NoteTemplate lineage transition. It
// never prints connection material, credentials, template identifiers, or raw
// database errors. Preflight, approval, the session lock, and every mutation
// use one retained PostgreSQL connection.

import { createHash } from "node:crypto";
import { performance } from "node:perf_hooks";

import { Pool, type PoolClient } from "pg";

import {
  buildDatabaseConnectionString,
  DATABASE_SEARCH_PATH,
} from "../src/database-connection-string";
import { assertNonProdDatabase, describeDbTarget } from "../src/db-guard";
import {
  backfillLineageBatch,
  buildLineageGuardIndex,
  buildLineageIndexes,
  contractLineageNotNull,
  LINEAGE_OPERATION_KEY,
  LINEAGE_PROOF_CONTRACT_VERSION,
  readLineageMigrationStatusSnapshot,
  recordLineageMigrationFailure,
  validateLineageContract,
  type LineageMigrationPhase,
  type LineageMigrationStatus,
  type RawSqlClient,
  type TransactionalRawSqlClient,
} from "../src/template-twin-lineage-online";
import { acquireLineageOperatorSessionLockOnClient } from "../src/template-twin-lineage-session-lock";

export type LineageOperatorPhase =
  | "status"
  | "guard-index"
  | "backfill"
  | "indexes"
  | "validate"
  | "contract";
type MutatingPhase = Exclude<LineageOperatorPhase, "status">;

interface Options {
  phase: LineageOperatorPhase;
  batchSize: number;
  batchDelayMs: number;
  maxBatches: number | null;
}

interface ConfiguredTarget {
  host: string;
  port: number;
  database: string;
  login: string;
}

export interface LineageOperatorTarget extends ConfiguredTarget {
  serverAddress: string;
  serverPort: number;
  serverVersionNumber: number;
  systemIdentifier: string;
  tlsIdentity: string;
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
  databaseOwner: string;
  principalCanLogin: boolean;
  principalSuperuser: boolean;
  inRecovery: boolean;
}

const APPLICATION_NAME = "quillmd_template_twin_lineage_online_v1";
const LINEAGE_OPERATOR_PRINCIPAL = "meddoc";
const LOCK_TIMEOUT_MS = 2_000;
const SHORT_STATEMENT_TIMEOUT_MS = 30_000;
const INDEX_STATEMENT_TIMEOUT_MS = 15 * 60_000;
const TARGET_FINGERPRINT_VERSION = "quillmd-template-twin-lineage-target-v2";
const MUTATING_PHASES = [
  "guard-index",
  "backfill",
  "indexes",
  "validate",
  "contract",
] as const;
const ALLOWED_QUERY_KEYS = new Set([
  "schema",
  "options",
  "sslmode",
  "sslcert",
  "sslkey",
  "sslrootcert",
  "channel_binding",
]);

function integer(value: string, flag: string, minimum: number): number {
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < minimum) {
    throw new Error(`${flag} requires an integer >= ${minimum}`);
  }
  return parsed;
}

export function parseLineageOperatorArgs(args: string[]): Options {
  let phase: LineageOperatorPhase | null = null;
  let batchSize = 1_000;
  let batchDelayMs = 100;
  let maxBatches: number | null = null;
  const seen = new Set<string>();
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index]!;
    if (seen.has(arg)) throw new Error(`Duplicate argument: ${arg}`);
    seen.add(arg);
    if (arg === "--phase") {
      const value = args[++index] as LineageOperatorPhase | undefined;
      if (
        !value ||
        ![
          "status",
          "guard-index",
          "backfill",
          "indexes",
          "validate",
          "contract",
        ].includes(value)
      ) {
        throw new Error("LINEAGE_MIGRATION_PHASE_INVALID");
      }
      phase = value;
    } else if (arg === "--batch-size") {
      batchSize = integer(args[++index] ?? "", arg, 1);
    } else if (arg === "--batch-delay-ms") {
      batchDelayMs = integer(args[++index] ?? "", arg, 0);
    } else if (arg === "--max-batches") {
      maxBatches = integer(args[++index] ?? "", arg, 1);
    } else {
      throw new Error("LINEAGE_MIGRATION_ARGUMENT_INVALID");
    }
  }
  if (!phase) throw new Error("LINEAGE_MIGRATION_PHASE_REQUIRED");
  return { phase, batchSize, batchDelayMs, maxBatches };
}

function statementTimeoutMs(phase: LineageOperatorPhase): number {
  return phase === "guard-index" || phase === "indexes"
    ? INDEX_STATEMENT_TIMEOUT_MS
    : SHORT_STATEMENT_TIMEOUT_MS;
}

function assertOperatorQueryContract(connectionString: string): void {
  const url = new URL(connectionString);
  for (const [key, value] of url.searchParams) {
    if (!ALLOWED_QUERY_KEYS.has(key)) {
      throw new Error("LINEAGE_MIGRATION_CONNECTION_QUERY_INVALID");
    }
    if (key === "schema" && value !== "public") {
      throw new Error("LINEAGE_MIGRATION_CONNECTION_QUERY_INVALID");
    }
  }
}

export function buildLineageOperatorConnectionString(
  databaseUrl: string,
  phase: LineageOperatorPhase,
): string {
  const connectionString = buildDatabaseConnectionString(
    databaseUrl,
    statementTimeoutMs(phase),
    {
      lockTimeoutMs: LOCK_TIMEOUT_MS,
      applicationName: APPLICATION_NAME,
      defaultTransactionReadOnly: phase === "status",
    },
  );
  assertOperatorQueryContract(connectionString);
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
  if (
    !target.host ||
    !target.database ||
    !target.login ||
    !Number.isSafeInteger(target.port) ||
    target.port < 1 ||
    target.port > 65_535
  ) {
    throw new Error("LINEAGE_MIGRATION_TARGET_INVALID");
  }
  return target;
}

function normalizeTlsFingerprint(value: string): string {
  const normalized = value.replaceAll(":", "").toLowerCase();
  if (!/^[a-f0-9]{64}$/u.test(normalized)) {
    throw new Error("LINEAGE_MIGRATION_SESSION_TARGET_MISMATCH");
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
      throw new Error("LINEAGE_MIGRATION_SESSION_TARGET_MISMATCH");
    }
    return "plaintext";
  }
  if (
    stream?.encrypted !== true ||
    typeof stream.getPeerCertificate !== "function"
  ) {
    throw new Error("LINEAGE_MIGRATION_SESSION_TARGET_MISMATCH");
  }
  const fingerprint = stream.getPeerCertificate().fingerprint256;
  if (!fingerprint) {
    throw new Error("LINEAGE_MIGRATION_SESSION_TARGET_MISMATCH");
  }
  return `x509-${stream.authorized === true ? "authorized" : "unverified"}-sha256:${normalizeTlsFingerprint(fingerprint)}`;
}

export async function preflightLineageOperatorTarget(
  client: PoolClient,
  expected: ConfiguredTarget,
  phase: LineageOperatorPhase,
): Promise<LineageOperatorTarget> {
  const result = await client.query<SessionTargetRow>(`
    SELECT session_user::TEXT AS "sessionRole",
           current_user::TEXT AS "currentRole",
           current_database()::TEXT AS "database",
           pg_catalog.inet_server_addr()::TEXT AS "serverAddress",
           pg_catalog.inet_server_port() AS "serverPort",
           current_setting('server_version_num')::INTEGER
             AS "serverVersionNumber",
           (SELECT control.system_identifier::TEXT
              FROM pg_catalog.pg_control_system() control)
             AS "systemIdentifier",
           current_setting('search_path') AS "searchPath",
           (SELECT setting::INTEGER FROM pg_catalog.pg_settings
             WHERE name = 'statement_timeout') AS "statementTimeoutMs",
           (SELECT setting::INTEGER FROM pg_catalog.pg_settings
             WHERE name = 'lock_timeout') AS "lockTimeoutMs",
           current_setting('application_name') AS "applicationName",
           current_setting('transaction_read_only') AS "transactionReadOnly",
           COALESCE((SELECT ssl FROM pg_catalog.pg_stat_ssl
             WHERE pid = pg_catalog.pg_backend_pid()), FALSE) AS "ssl",
           database_owner.rolname::TEXT AS "databaseOwner",
           principal.rolcanlogin AS "principalCanLogin",
           principal.rolsuper AS "principalSuperuser",
           pg_catalog.pg_is_in_recovery() AS "inRecovery"
      FROM pg_catalog.pg_database database_state
      JOIN pg_catalog.pg_roles database_owner
        ON database_owner.oid = database_state.datdba
      JOIN pg_catalog.pg_roles principal
        ON principal.rolname = session_user
     WHERE database_state.datname = pg_catalog.current_database()
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
    expected.login !== LINEAGE_OPERATOR_PRINCIPAL ||
    row.sessionRole !== LINEAGE_OPERATOR_PRINCIPAL ||
    row.currentRole !== LINEAGE_OPERATOR_PRINCIPAL ||
    row.database !== expected.database ||
    !row.serverAddress ||
    !Number.isSafeInteger(row.serverPort) ||
    row.serverPort! < 1 ||
    row.serverPort! > 65_535 ||
    Math.trunc(row.serverVersionNumber / 10_000) !== 16 ||
    !/^[0-9]+$/u.test(row.systemIdentifier) ||
    row.searchPath !== DATABASE_SEARCH_PATH ||
    row.statementTimeoutMs !== statementTimeoutMs(phase) ||
    row.lockTimeoutMs !== LOCK_TIMEOUT_MS ||
    row.applicationName !== APPLICATION_NAME ||
    row.transactionReadOnly !== (phase === "status" ? "on" : "off") ||
    row.databaseOwner !== LINEAGE_OPERATOR_PRINCIPAL ||
    row.principalCanLogin !== true ||
    row.principalSuperuser !== true
  ) {
    throw new Error("LINEAGE_MIGRATION_SESSION_TARGET_MISMATCH");
  }
  return {
    ...expected,
    serverAddress: row.serverAddress.toLowerCase(),
    serverPort: row.serverPort,
    serverVersionNumber: row.serverVersionNumber,
    systemIdentifier: row.systemIdentifier,
    tlsIdentity: actualTlsIdentity(client, row.ssl),
    inRecovery: row.inRecovery,
  };
}

function protocolEpoch(status: LineageMigrationStatus): string {
  return createHash("sha256")
    .update(
      JSON.stringify([
        "quillmd-template-twin-lineage-protocol-epoch-v1",
        LINEAGE_PROOF_CONTRACT_VERSION,
        status.phase,
        status.rowsProcessed,
        status.batchCount,
        status.lastProcessedId,
        status.updatedAt,
        status.nullRows,
        status.duplicateLineageVersions,
        status.partialIndex,
        status.finalIndex,
        status.templateKindIndex,
        status.validationConstraint,
        status.presentIndexesExact,
        status.validationConstraintExact,
        status.columnNotNull,
        status.transitionTriggerPresent,
        status.transitionContractExact,
      ]),
      "utf8",
    )
    .digest("hex");
}

export function lineageOperatorTargetFingerprint(
  target: LineageOperatorTarget,
  phase: MutatingPhase,
  expectedProgressPhase: LineageMigrationPhase,
  epoch: string,
): string {
  return createHash("sha256")
    .update(
      JSON.stringify([
        TARGET_FINGERPRINT_VERSION,
        LINEAGE_PROOF_CONTRACT_VERSION,
        ["host", target.host],
        ["port", target.port],
        ["database", target.database],
        ["login", target.login],
        ["tlsIdentity", target.tlsIdentity],
        ["serverAddress", target.serverAddress],
        ["serverPort", target.serverPort],
        ["serverVersionNumber", target.serverVersionNumber],
        ["systemIdentifier", target.systemIdentifier],
        ["approvedPrincipal", LINEAGE_OPERATOR_PRINCIPAL],
        ["inRecovery", target.inRecovery],
        ["phase", phase],
        ["expectedProgressPhase", expectedProgressPhase],
        ["protocolEpoch", epoch],
      ]),
      "utf8",
    )
    .digest("hex");
}

export function lineageOperatorApprovalFingerprint(
  target: LineageOperatorTarget,
  status: LineageMigrationStatus,
  phase: MutatingPhase,
): string {
  return lineageOperatorTargetFingerprint(
    target,
    phase,
    status.phase,
    protocolEpoch(status),
  );
}

function targetFingerprints(
  target: LineageOperatorTarget,
  status: LineageMigrationStatus,
): Partial<Record<MutatingPhase, string>> {
  if (target.inRecovery) return {};
  const epoch = protocolEpoch(status);
  return Object.fromEntries(
    MUTATING_PHASES.map((phase) => [
      phase,
      lineageOperatorTargetFingerprint(target, phase, status.phase, epoch),
    ]),
  );
}

export function assertApprovedLineageOperatorTarget(
  target: LineageOperatorTarget,
  status: LineageMigrationStatus,
  phase: MutatingPhase,
  approvedFingerprint: string | undefined,
): void {
  if (target.inRecovery) {
    throw new Error("LINEAGE_MIGRATION_TARGET_IN_RECOVERY");
  }
  if (!approvedFingerprint || !/^[a-f0-9]{64}$/u.test(approvedFingerprint)) {
    throw new Error("LINEAGE_MIGRATION_TARGET_APPROVAL_REQUIRED");
  }
  const expected = lineageOperatorApprovalFingerprint(target, status, phase);
  if (approvedFingerprint !== expected) {
    throw new Error("LINEAGE_MIGRATION_TARGET_APPROVAL_MISMATCH");
  }
}

function assertMutationAuthorized(
  databaseUrl: string,
  phase: MutatingPhase,
): void {
  try {
    assertNonProdDatabase(databaseUrl);
  } catch (nonProductionError) {
    const target = describeDbTarget(databaseUrl);
    const changeId =
      process.env.TEMPLATE_TWIN_LINEAGE_PRODUCTION_CHANGE_ID?.trim();
    if (
      process.env.TEMPLATE_TWIN_LINEAGE_ALLOW_PRODUCTION !== "true" ||
      !changeId ||
      changeId.length > 128 ||
      process.env.TEMPLATE_TWIN_LINEAGE_PRODUCTION_ACK !==
        `${target.database}:${phase}`
    ) {
      throw nonProductionError;
    }
  }
  if (
    phase === "contract" &&
    process.env.TEMPLATE_TWIN_LINEAGE_CONTRACT_ACK !==
      `${LINEAGE_OPERATION_KEY}:${describeDbTarget(databaseUrl).database}`
  ) {
    throw new Error("LINEAGE_MIGRATION_CONTRACT_ACK_REQUIRED");
  }
}

export function createLineageSessionClient(
  connection: PoolClient,
): TransactionalRawSqlClient {
  let transactionActive = false;
  const raw: TransactionalRawSqlClient = {
    $executeRawUnsafe: async (query: string, ...values: unknown[]) => {
      const result = await connection.query(query, values);
      return result.rowCount ?? 0;
    },
    $queryRawUnsafe: async <T>(query: string, ...values: unknown[]) => {
      const result = await connection.query(query, values);
      return result.rows as T;
    },
    $transaction: async <T>(
      callback: (tx: RawSqlClient) => Promise<T>,
    ): Promise<T> => {
      if (transactionActive) {
        throw new Error("LINEAGE_MIGRATION_NESTED_TRANSACTION_INVALID");
      }
      await connection.query("BEGIN");
      transactionActive = true;
      try {
        const result = await callback(raw);
        await connection.query("COMMIT");
        transactionActive = false;
        return result;
      } catch (error) {
        try {
          await connection.query("ROLLBACK");
        } finally {
          transactionActive = false;
        }
        throw error;
      }
    },
  };
  return raw;
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function printSafe(value: unknown): void {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

export function lineageStatusForOutput(status: LineageMigrationStatus): Omit<
  LineageMigrationStatus,
  "lastProcessedId"
> & {
  cursorPresent: boolean;
} {
  const { lastProcessedId, ...safeStatus } = status;
  return { ...safeStatus, cursorPresent: lastProcessedId !== null };
}

const SAFE_ERROR_CODES = new Set([
  "DUPLICATE_LINEAGE_VERSION",
  "LINEAGE_MIGRATION_ARGUMENT_INVALID",
  "LINEAGE_MIGRATION_BACKFILL_PHASE_ALREADY_ADVANCED",
  "LINEAGE_MIGRATION_BACKFILL_PHASE_REQUIRES_GUARD",
  "LINEAGE_MIGRATION_BACKFILL_REQUIRES_GUARD_INDEX",
  "LINEAGE_MIGRATION_BATCH_RESULT_MISSING",
  "LINEAGE_MIGRATION_BATCH_SIZE_MUST_BE_1_TO_10000",
  "LINEAGE_MIGRATION_COLUMN_MISSING",
  "LINEAGE_MIGRATION_COLUMN_NOT_CONTRACTED",
  "LINEAGE_MIGRATION_CONSTRAINT_CATALOG_AMBIGUOUS",
  "LINEAGE_MIGRATION_CONSTRAINT_DEFINITION_MISMATCH",
  "LINEAGE_MIGRATION_CONSTRAINT_MISSING",
  "LINEAGE_MIGRATION_CONTRACT_ACK_REQUIRED",
  "LINEAGE_MIGRATION_CONTRACT_PROOF_INCOMPLETE",
  "LINEAGE_MIGRATION_CONTRACT_REQUIRES_VALIDATION",
  "LINEAGE_MIGRATION_DUPLICATE_LINEAGE_VERSIONS",
  "LINEAGE_MIGRATION_GUARD_PHASE_ALREADY_ADVANCED",
  "LINEAGE_MIGRATION_INDEX_CATALOG_AMBIGUOUS",
  "LINEAGE_MIGRATION_INDEX_DEFINITION_MISMATCH",
  "LINEAGE_MIGRATION_INDEX_MISSING",
  "LINEAGE_MIGRATION_INDEX_NAME_INEXACT",
  "LINEAGE_MIGRATION_INDEX_PHASE_REQUIRES_BACKFILL",
  "LINEAGE_MIGRATION_INVALID_INDEX_DEFINITION_MISMATCH",
  "LINEAGE_MIGRATION_INVALID_BATCH_COUNT",
  "LINEAGE_MIGRATION_INVALID_DUPLICATE_ROWS",
  "LINEAGE_MIGRATION_INVALID_LAST_BATCH_ROWS",
  "LINEAGE_MIGRATION_INVALID_NULL_ROWS",
  "LINEAGE_MIGRATION_INVALID_ROWS_PROCESSED",
  "LINEAGE_MIGRATION_NULL_ROWS_REMAIN",
  "LINEAGE_MIGRATION_OPERATOR_BUSY",
  "LINEAGE_MIGRATION_PARTIAL_INDEX_REMAINS",
  "LINEAGE_MIGRATION_PHASE_INVALID",
  "LINEAGE_MIGRATION_PHASE_REQUIRED",
  "LINEAGE_MIGRATION_PROGRESS_ROW_MISSING",
  "LINEAGE_MIGRATION_SESSION_TARGET_MISMATCH",
  "LINEAGE_MIGRATION_STALE_PHASE_TRANSITION",
  "LINEAGE_MIGRATION_TARGET_APPROVAL_MISMATCH",
  "LINEAGE_MIGRATION_TARGET_APPROVAL_REQUIRED",
  "LINEAGE_MIGRATION_TARGET_IN_RECOVERY",
  "LINEAGE_MIGRATION_TRANSITION_ARTIFACT_REMAINS",
  "LINEAGE_MIGRATION_TRANSITION_ARTIFACT_STATE_INVALID",
  "LINEAGE_MIGRATION_TRANSITION_TRIGGER_AMBIGUOUS",
  "LINEAGE_MIGRATION_TRANSITION_TRIGGER_MISMATCH",
  "LINEAGE_MIGRATION_UNEXPECTED_INDEX_PRESENT",
  "LINEAGE_MIGRATION_VALIDATION_PHASE_REQUIRES_INDEXES",
  "LINEAGE_MIGRATION_VALIDATION_REQUIRES_VALID_INDEXES",
  "LOCK_TIMEOUT",
  "STATEMENT_TIMEOUT",
]);

export function safeLineageOperatorErrorCode(error: unknown): string {
  return error instanceof Error && SAFE_ERROR_CODES.has(error.message)
    ? error.message
    : "LINEAGE_MIGRATION_OPERATOR_FAILED";
}

export function safeLineageOperatorDiagnosticCode(
  error: unknown,
  stage: string,
): string {
  const allowlisted = safeLineageOperatorErrorCode(error);
  if (allowlisted !== "LINEAGE_MIGRATION_OPERATOR_FAILED") return allowlisted;
  const candidate =
    typeof error === "object" && error !== null && "code" in error
      ? String((error as { code?: unknown }).code ?? "")
      : "";
  if (/^[A-Z0-9]{5}$/u.test(candidate)) {
    return `LINEAGE_MIGRATION_DATABASE_${candidate}`;
  }
  const safeStage = /^[A-Z][A-Z0-9_]{1,80}$/u.test(stage) ? stage : "OPERATOR";
  return `LINEAGE_MIGRATION_${safeStage}_FAILED`;
}

async function run(): Promise<void> {
  let pool: Pool | null = null;
  let connection: PoolClient | null = null;
  let client: TransactionalRawSqlClient | null = null;
  let operatorLock: Awaited<
    ReturnType<typeof acquireLineageOperatorSessionLockOnClient>
  > | null = null;
  let mutationAdmitted = false;
  let diagnosticStage = "ARGUMENTS";
  let stopping = false;
  const stop = () => {
    stopping = true;
  };
  process.once("SIGINT", stop);
  process.once("SIGTERM", stop);

  try {
    const options = parseLineageOperatorArgs(process.argv.slice(2));
    diagnosticStage = "CONNECTION_STRING";
    const databaseUrl = process.env.DATABASE_URL;
    if (!databaseUrl)
      throw new Error("LINEAGE_MIGRATION_DATABASE_URL_REQUIRED");
    const connectionString = buildLineageOperatorConnectionString(
      databaseUrl,
      options.phase,
    );
    const expectedTarget = configuredTarget(connectionString);
    pool = new Pool({
      connectionString,
      max: 1,
      connectionTimeoutMillis: 10_000,
    });
    diagnosticStage = "CONNECT";
    connection = await pool.connect();
    client = createLineageSessionClient(connection);
    diagnosticStage = "TARGET_PREFLIGHT";
    const liveTarget = await preflightLineageOperatorTarget(
      connection,
      expectedTarget,
      options.phase,
    );
    diagnosticStage = "STATUS_SNAPSHOT";
    const observedStatus = await readLineageMigrationStatusSnapshot(client);

    if (options.phase === "status") {
      printSafe({
        event: "status",
        readOnly: true,
        targetFingerprints: targetFingerprints(liveTarget, observedStatus),
        ...lineageStatusForOutput(observedStatus),
      });
      return;
    }

    diagnosticStage = "TARGET_APPROVAL";
    assertApprovedLineageOperatorTarget(
      liveTarget,
      observedStatus,
      options.phase,
      process.env.TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT,
    );
    diagnosticStage = "MUTATION_AUTHORIZATION";
    assertMutationAuthorized(connectionString, options.phase);
    diagnosticStage = "SESSION_LOCK";
    operatorLock = await acquireLineageOperatorSessionLockOnClient(connection);
    diagnosticStage = "LOCKED_STATUS";
    const lockedStatus = await readLineageMigrationStatusSnapshot(client);
    if (protocolEpoch(lockedStatus) !== protocolEpoch(observedStatus)) {
      throw new Error("LINEAGE_MIGRATION_TARGET_APPROVAL_MISMATCH");
    }
    mutationAdmitted = true;
    diagnosticStage = `${options.phase.replaceAll("-", "_").toUpperCase()}_EXECUTION`;

    if (options.phase === "backfill") {
      let batchesThisRun = 0;
      while (!stopping) {
        const batchStarted = performance.now();
        const result = await backfillLineageBatch(client, options.batchSize);
        const durationMs =
          Math.round((performance.now() - batchStarted) * 100) / 100;
        if (result.batchRows > 0) batchesThisRun += 1;
        const { lastProcessedId, ...safeResult } = result;
        printSafe({
          event: "batch",
          durationMs,
          ...safeResult,
          cursorPresent: lastProcessedId !== null,
        });
        if (result.complete || stopping) break;
        if (
          options.maxBatches !== null &&
          batchesThisRun >= options.maxBatches
        ) {
          printSafe({ event: "paused", reason: "max_batches", batchesThisRun });
          break;
        }
        if (options.batchDelayMs > 0) await sleep(options.batchDelayMs);
      }
    } else if (options.phase === "guard-index") {
      await buildLineageGuardIndex(client);
    } else if (options.phase === "indexes") {
      await buildLineageIndexes(client);
    } else if (options.phase === "validate") {
      await validateLineageContract(client);
    } else {
      await contractLineageNotNull(client);
    }
    printSafe({
      event: "status",
      ...lineageStatusForOutput(
        await readLineageMigrationStatusSnapshot(client),
      ),
    });
  } catch (error) {
    let outputError = error;
    if (mutationAdmitted && client) {
      try {
        outputError = new Error(
          await recordLineageMigrationFailure(client, error),
        );
      } catch {
        // Failure evidence may be unavailable if the expand boundary was not
        // admitted. Preserve a fixed external code and never expose details.
      }
    }
    const outputCode = safeLineageOperatorDiagnosticCode(
      outputError,
      diagnosticStage,
    );
    process.stderr.write(`${outputCode}\n`);
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
    connection?.release();
    if (pool) {
      try {
        await pool.end();
      } catch {
        cleanupFailed = true;
      }
    }
    if (cleanupFailed) {
      process.stderr.write("LINEAGE_MIGRATION_CLEANUP_FAILED\n");
      process.exitCode = 1;
    }
  }
}

if (process.env.VITEST !== "true") {
  void run().catch(() => {
    process.stderr.write("LINEAGE_MIGRATION_OPERATOR_FAILED\n");
    process.exitCode = 1;
  });
}
