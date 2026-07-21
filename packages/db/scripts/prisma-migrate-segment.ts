#!/usr/bin/env tsx

// Closed, cumulative Prisma migration runner for the two online transition
// boundaries in this release. It never offers an arbitrary cutoff or an
// "all" mode, never edits Prisma's ledger, and never prints connection data.

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  chmodSync,
  cpSync,
  lstatSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  symlinkSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { Pool, type PoolClient } from "pg";

import { readAuthTokenLinearizationStatus } from "../src/auth-token-linearization-online";
import {
  buildDatabaseConnectionString,
  parseStatementTimeoutMs,
} from "../src/database-connection-string";
import { assertNonProdDatabase, describeDbTarget } from "../src/db-guard";
import {
  assertExactLineageContractCatalog,
  LINEAGE_OPERATION_KEY,
  readLineageMigrationStatusSnapshot,
  type RawSqlClient,
  type TransactionalRawSqlClient,
} from "../src/template-twin-lineage-online";

export const PRISMA_MIGRATION_SEGMENTS = Object.freeze({
  "lineage-expand": Object.freeze({
    count: 68,
    minimumApplied: 0,
    lastMigration: "20260715162000_template_twin_docx_v1",
    requiresLineage: false,
    requiresAuth: false,
    requiresReleaseSecurity: false,
  }),
  "auth-expand": Object.freeze({
    count: 93,
    minimumApplied: 68,
    lastMigration: "20260720150000_auth_token_linearization_v5",
    requiresLineage: true,
    requiresAuth: false,
    requiresReleaseSecurity: false,
  }),
  "pre-v9": Object.freeze({
    count: 96,
    minimumApplied: 93,
    lastMigration: "20260720200000_mfa_credential_lifecycle_audit_v8",
    requiresLineage: true,
    requiresAuth: true,
    requiresReleaseSecurity: false,
  }),
  v9: Object.freeze({
    count: 97,
    minimumApplied: 96,
    lastMigration: "20260720213000_exact_database_principal_closure_v9",
    requiresLineage: true,
    requiresAuth: true,
    requiresReleaseSecurity: true,
  }),
} as const);

type MigrationSegment = keyof typeof PRISMA_MIGRATION_SEGMENTS;
type OperatorPhase = MigrationSegment | "status";

interface MigrationSource {
  name: string;
  directory: string;
  sqlPath: string;
  checksum: string;
}

interface LedgerRow {
  migrationName: string;
  checksum: string;
  finished: boolean;
  notRolledBack: boolean;
  appliedStepsCount: number;
}

interface LedgerAttemptRow {
  id: string;
  migrationName: string;
  checksum: string;
  finished: boolean;
  rolledBack: boolean;
  appliedStepsCount: number;
}

interface TargetRow {
  databaseName: string;
  sessionRole: string;
  currentRole: string;
  serverVersionNumber: number;
  systemIdentifier: string;
  ownerIsExact: boolean;
  inRecovery: boolean;
  ssl: boolean;
  clientAddress: string | null;
  serverAddress: string | null;
}

interface TargetProof {
  fingerprint: string;
  inRecovery: boolean;
}

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(packageRoot, "../..");
const prismaRoot = join(packageRoot, "prisma");
const migrationsRoot = join(prismaRoot, "migrations");
const expectedMigrationCount = 97;
const databaseOwner = "meddoc";
const defaultMigrationLockTimeoutMs = 5_000;
const migrationNetworkBoundary = "postgres-loopback-v1";

interface DatabaseReleaseMigrationEnvironment {
  readonly [name: string]: string | undefined;
  PRISMA_STATEMENT_TIMEOUT_MS?: string;
  DATABASE_RELEASE_MIGRATION_LOCK_TIMEOUT_MS?: string;
  DATABASE_RELEASE_MIGRATION_NETWORK_BOUNDARY?: string;
}

interface MigrationTimeoutContract {
  statementTimeoutMs: number;
  lockTimeoutMs: number;
}

function sha256(bytes: Buffer | string): string {
  return createHash("sha256").update(bytes).digest("hex");
}

export function resolveMigrationTimeoutContract(
  environment: Readonly<DatabaseReleaseMigrationEnvironment>,
): MigrationTimeoutContract {
  return {
    statementTimeoutMs: parseStatementTimeoutMs(
      environment.PRISMA_STATEMENT_TIMEOUT_MS,
    ),
    lockTimeoutMs: parseStatementTimeoutMs(
      environment.DATABASE_RELEASE_MIGRATION_LOCK_TIMEOUT_MS ??
        defaultMigrationLockTimeoutMs,
    ),
  };
}

export function buildMigrationProbeConnectionString(input: {
  databaseUrl: string;
  phase: OperatorPhase;
  environment: Readonly<DatabaseReleaseMigrationEnvironment>;
}): string {
  const timeout = resolveMigrationTimeoutContract(input.environment);
  return buildDatabaseConnectionString(
    input.databaseUrl,
    timeout.statementTimeoutMs,
    {
      lockTimeoutMs: timeout.lockTimeoutMs,
      applicationName: "quillmd_prisma_migrate_segment_probe_v1",
      defaultTransactionReadOnly: input.phase === "status",
    },
  );
}

export function buildMigrationDeployConnectionString(input: {
  databaseUrl: string;
  environment: Readonly<DatabaseReleaseMigrationEnvironment>;
}): string {
  const timeout = resolveMigrationTimeoutContract(input.environment);
  return buildDatabaseConnectionString(
    input.databaseUrl,
    timeout.statementTimeoutMs,
    {
      lockTimeoutMs: timeout.lockTimeoutMs,
      applicationName: "quillmd_prisma_migrate_segment_deploy_v1",
    },
  );
}

export function buildPrismaMigrationChildEnvironment(
  connectionString: string,
  environment: Readonly<NodeJS.ProcessEnv>,
): NodeJS.ProcessEnv {
  return {
    PATH: environment.PATH,
    DATABASE_URL: connectionString,
    CI: environment.CI,
    NO_COLOR: "1",
    PRISMA_HIDE_UPDATE_MESSAGE: "1",
  };
}

export function parsePrismaMigrationSegmentArgs(args: string[]): OperatorPhase {
  if (args.length !== 2 || args[0] !== "--phase") {
    throw new Error("DATABASE_RELEASE_MIGRATION_PHASE_REQUIRED");
  }
  const phase = args[1];
  if (
    phase !== "status" &&
    !Object.prototype.hasOwnProperty.call(PRISMA_MIGRATION_SEGMENTS, phase)
  ) {
    throw new Error("DATABASE_RELEASE_MIGRATION_PHASE_INVALID");
  }
  return phase as OperatorPhase;
}

export function readExactMigrationSources(): MigrationSource[] {
  const entries = readdirSync(migrationsRoot, { withFileTypes: true });
  const directories = entries
    .filter((entry) => entry.isDirectory() && !entry.isSymbolicLink())
    .map((entry) => entry.name)
    .sort((left, right) => Buffer.from(left).compare(Buffer.from(right)));
  assert.equal(directories.length, expectedMigrationCount);

  const sources = directories.map((name) => {
    assert.match(name, /^(?:0000_init|[0-9]{14}_[a-z0-9_]+)$/u);
    const directory = join(migrationsRoot, name);
    const children = readdirSync(directory);
    assert.deepEqual(children, ["migration.sql"]);
    const sqlPath = join(directory, "migration.sql");
    const metadata = lstatSync(sqlPath);
    assert(metadata.isFile() && !metadata.isSymbolicLink());
    return {
      name,
      directory,
      sqlPath,
      checksum: sha256(readFileSync(sqlPath)),
    };
  });

  for (const segment of Object.values(PRISMA_MIGRATION_SEGMENTS)) {
    assert.equal(sources[segment.count - 1]?.name, segment.lastMigration);
  }
  return sources;
}

export function assertExactLedgerPrefix(
  ledger: readonly LedgerRow[],
  sources: readonly MigrationSource[],
): void {
  assert(ledger.length <= sources.length);
  ledger.forEach((row, index) => {
    const expected = sources[index];
    assert(expected);
    assert.equal(row.migrationName, expected.name);
    assert.equal(row.checksum, expected.checksum);
    assert.equal(row.finished, true);
    assert.equal(row.notRolledBack, true);
    assert(row.appliedStepsCount > 0);
  });
}

export function normalizePrismaLedgerAttempts(
  attempts: readonly LedgerAttemptRow[],
  sources: readonly MigrationSource[],
): LedgerRow[] {
  const sourceOrdinal = new Map(
    sources.map((source, index) => [source.name, index] as const),
  );
  const successful = new Map<string, LedgerRow>();
  for (const attempt of attempts) {
    const ordinal = sourceOrdinal.get(attempt.migrationName);
    assert.notEqual(ordinal, undefined);
    const expected = sources[ordinal!];
    assert(expected);
    assert.equal(attempt.checksum, expected.checksum);
    assert.equal(attempt.finished === attempt.rolledBack, false);
    assert(Number.isSafeInteger(attempt.appliedStepsCount));
    assert(attempt.appliedStepsCount >= 0);
    if (attempt.finished) {
      assert(attempt.appliedStepsCount > 0);
      assert(!successful.has(attempt.migrationName));
      successful.set(attempt.migrationName, {
        migrationName: attempt.migrationName,
        checksum: attempt.checksum,
        finished: true,
        notRolledBack: true,
        appliedStepsCount: attempt.appliedStepsCount,
      });
    }
  }

  const normalized = sources
    .filter((source) => successful.has(source.name))
    .map((source) => successful.get(source.name)!);
  assertExactLedgerPrefix(normalized, sources);

  // A resolved failed attempt may remain as durable evidence for any already
  // successful migration or for exactly the next migration awaiting retry.
  // A rolled-back future gap is not a valid official Prisma history.
  for (const attempt of attempts) {
    if (!attempt.rolledBack) continue;
    const ordinal = sourceOrdinal.get(attempt.migrationName);
    assert.notEqual(ordinal, undefined);
    assert(ordinal! <= normalized.length);
  }
  return normalized;
}

async function readLedger(
  client: PoolClient,
  sources: readonly MigrationSource[],
): Promise<LedgerRow[]> {
  const existence = await client.query<{ exists: boolean }>(
    `SELECT pg_catalog.to_regclass(
       'public."_prisma_migrations"'
     ) IS NOT NULL AS "exists"`,
  );
  if (existence.rows[0]?.exists !== true) return [];
  const result = await client.query<LedgerAttemptRow>(
    `SELECT id::TEXT AS "id",
            migration_name::TEXT AS "migrationName",
            checksum::TEXT AS "checksum",
            finished_at IS NOT NULL AS "finished",
            rolled_back_at IS NOT NULL AS "rolledBack",
            applied_steps_count::INTEGER AS "appliedStepsCount"
       FROM public."_prisma_migrations"
      ORDER BY started_at, id`,
  );
  return normalizePrismaLedgerAttempts(result.rows, sources);
}

function buildTargetFingerprint(row: TargetRow, databaseUrl: string): string {
  const url = new URL(databaseUrl);
  return sha256(
    JSON.stringify([
      "quillmd-database-release-migration-target-v2",
      url.protocol,
      url.hostname,
      url.port || "5432",
      url.username,
      row.databaseName,
      row.sessionRole,
      row.currentRole,
      row.serverVersionNumber,
      row.systemIdentifier,
      row.ownerIsExact,
      row.inRecovery,
      row.ssl,
      row.clientAddress,
      row.serverAddress,
    ]),
  );
}

export function databaseReleaseMigrationApprovalFingerprint(input: {
  targetFingerprint: string;
  phase: MigrationSegment;
  ledger: readonly Pick<LedgerRow, "migrationName" | "checksum">[];
  sources: readonly Pick<MigrationSource, "name" | "checksum">[];
}): string {
  const segment = PRISMA_MIGRATION_SEGMENTS[input.phase];
  return sha256(
    JSON.stringify([
      "quillmd-database-release-migration-approval-v2",
      input.targetFingerprint,
      input.phase,
      segment.minimumApplied,
      segment.count,
      segment.lastMigration,
      input.ledger.map((entry) => [entry.migrationName, entry.checksum]),
      input.sources
        .slice(0, segment.count)
        .map((source) => [source.name, source.checksum]),
    ]),
  );
}

function migrationApprovalFingerprints(input: {
  targetFingerprint: string;
  inRecovery: boolean;
  ledger: readonly LedgerRow[];
  sources: readonly MigrationSource[];
}): Partial<Record<MigrationSegment, string>> {
  if (input.inRecovery) return {};
  return Object.fromEntries(
    (Object.keys(PRISMA_MIGRATION_SEGMENTS) as MigrationSegment[])
      .filter((phase) => {
        const segment = PRISMA_MIGRATION_SEGMENTS[phase];
        return (
          input.ledger.length >= segment.minimumApplied &&
          input.ledger.length <= segment.count
        );
      })
      .map((phase) => [
        phase,
        databaseReleaseMigrationApprovalFingerprint({
          targetFingerprint: input.targetFingerprint,
          phase,
          ledger: input.ledger,
          sources: input.sources,
        }),
      ]),
  );
}

export function assertMigrationNetworkTargetBoundary(input: {
  databaseUrl: string;
  clientAddress: string | null;
  serverAddress: string | null;
  environment: Readonly<DatabaseReleaseMigrationEnvironment>;
}): void {
  const target = new URL(input.databaseUrl);
  if (
    input.environment.DATABASE_RELEASE_MIGRATION_NETWORK_BOUNDARY !==
      migrationNetworkBoundary ||
    target.hostname !== "127.0.0.1" ||
    target.port !== "5432" ||
    input.clientAddress !== "127.0.0.1" ||
    input.serverAddress !== "127.0.0.1"
  ) {
    throw new Error("DATABASE_RELEASE_MIGRATION_NETWORK_BOUNDARY_INVALID");
  }
}

async function proveTarget(
  client: PoolClient,
  databaseUrl: string,
  requireMutationBoundary: boolean,
  environment: Readonly<DatabaseReleaseMigrationEnvironment>,
): Promise<TargetProof> {
  const target = describeDbTarget(databaseUrl);
  const url = new URL(databaseUrl);
  if (url.username !== databaseOwner || (url.port && url.port !== "5432")) {
    throw new Error("DATABASE_RELEASE_MIGRATION_TARGET_INVALID");
  }
  const result = await client.query<TargetRow>(
    `SELECT pg_catalog.current_database()::TEXT AS "databaseName",
            session_user::TEXT AS "sessionRole",
            current_user::TEXT AS "currentRole",
            pg_catalog.current_setting('server_version_num')::INTEGER
              AS "serverVersionNumber",
            control.system_identifier::TEXT AS "systemIdentifier",
            EXISTS (
              SELECT 1
                FROM pg_catalog.pg_database database
                JOIN pg_catalog.pg_roles owner ON owner.oid = database.datdba
               WHERE database.datname = pg_catalog.current_database()
                 AND owner.rolname = session_user
                 AND owner.rolsuper
            ) AS "ownerIsExact",
            pg_catalog.pg_is_in_recovery() AS "inRecovery",
            COALESCE(ssl.ssl, FALSE) AS "ssl",
            pg_catalog.host(pg_catalog.inet_client_addr())
              AS "clientAddress",
            pg_catalog.host(pg_catalog.inet_server_addr())
              AS "serverAddress"
       FROM pg_catalog.pg_control_system() control
       LEFT JOIN pg_catalog.pg_stat_ssl ssl
         ON ssl.pid = pg_catalog.pg_backend_pid()`,
  );
  const row = result.rows[0];
  if (
    result.rowCount !== 1 ||
    !row ||
    row.databaseName !== target.database ||
    row.sessionRole !== databaseOwner ||
    row.currentRole !== databaseOwner ||
    Math.trunc(row.serverVersionNumber / 10_000) !== 16 ||
    !/^[0-9]+$/u.test(row.systemIdentifier) ||
    row.ownerIsExact !== true ||
    typeof row.inRecovery !== "boolean"
  ) {
    throw new Error("DATABASE_RELEASE_MIGRATION_TARGET_INVALID");
  }
  if (requireMutationBoundary) {
    if (row.inRecovery) {
      throw new Error("DATABASE_RELEASE_MIGRATION_TARGET_IN_RECOVERY");
    }
    assertMigrationNetworkTargetBoundary({
      databaseUrl,
      clientAddress: row.clientAddress,
      serverAddress: row.serverAddress,
      environment,
    });
  }
  return {
    fingerprint: buildTargetFingerprint(row, databaseUrl),
    inRecovery: row.inRecovery,
  };
}

function authorizeMutation(
  phase: MigrationSegment,
  databaseUrl: string,
  targetFingerprint: string,
): void {
  if (
    process.env.DATABASE_RELEASE_MIGRATION_APPROVED_TARGET_FINGERPRINT !==
    targetFingerprint
  ) {
    throw new Error("DATABASE_RELEASE_MIGRATION_TARGET_APPROVAL_REQUIRED");
  }
  try {
    assertNonProdDatabase(databaseUrl);
  } catch (nonProductionError) {
    const target = describeDbTarget(databaseUrl);
    const changeId =
      process.env.DATABASE_RELEASE_MIGRATION_PRODUCTION_CHANGE_ID?.trim();
    if (
      process.env.DATABASE_RELEASE_MIGRATION_ALLOW_PRODUCTION !== "true" ||
      !changeId ||
      changeId.length > 128 ||
      process.env.DATABASE_RELEASE_MIGRATION_PRODUCTION_ACK !==
        `${target.database}:${phase}`
    ) {
      throw nonProductionError;
    }
  }
}

function createPoolClientRawSqlClient(
  client: PoolClient,
): TransactionalRawSqlClient {
  let transactionActive = false;
  const raw: TransactionalRawSqlClient = {
    $executeRawUnsafe: async (query: string, ...values: unknown[]) => {
      const result = await client.query(query, values);
      return result.rowCount ?? 0;
    },
    $queryRawUnsafe: async <T>(query: string, ...values: unknown[]) => {
      const result = await client.query(query, values);
      return result.rows as T;
    },
    $transaction: async <T>(
      callback: (tx: RawSqlClient) => Promise<T>,
    ): Promise<T> => {
      if (transactionActive) {
        throw new Error(
          "DATABASE_RELEASE_MIGRATION_NESTED_TRANSACTION_INVALID",
        );
      }
      await client.query("BEGIN");
      transactionActive = true;
      try {
        const result = await callback(raw);
        await client.query("COMMIT");
        transactionActive = false;
        return result;
      } catch (error) {
        try {
          await client.query("ROLLBACK");
        } finally {
          transactionActive = false;
        }
        throw error;
      }
    },
  };
  return raw;
}

async function assertLineageContract(client: PoolClient): Promise<void> {
  const rawClient = createPoolClientRawSqlClient(client);
  const status = await readLineageMigrationStatusSnapshot(rawClient);
  if (
    status.operationKey !== LINEAGE_OPERATION_KEY ||
    status.phase !== "CONTRACTED" ||
    status.nullRows !== 0 ||
    status.duplicateLineageVersions !== 0 ||
    status.partialIndex.exists ||
    !status.finalIndex.exists ||
    !status.finalIndex.valid ||
    !status.finalIndex.ready ||
    !status.templateKindIndex.exists ||
    !status.templateKindIndex.valid ||
    !status.templateKindIndex.ready ||
    !status.validationConstraint.exists ||
    !status.validationConstraint.validated ||
    !status.presentIndexesExact ||
    !status.validationConstraintExact ||
    !status.columnNotNull ||
    status.transitionTriggerPresent ||
    !status.transitionContractExact
  ) {
    throw new Error("DATABASE_RELEASE_MIGRATION_LINEAGE_INCOMPLETE");
  }
  await assertExactLineageContractCatalog(rawClient);
}

async function assertAuthContract(client: PoolClient): Promise<void> {
  const status = await readAuthTokenLinearizationStatus(client);
  if (
    status.duplicateGroups !== 0 ||
    !status.indexExists ||
    !status.indexValid ||
    !status.indexReady ||
    !status.indexExact ||
    status.transitionTriggerEnabled ||
    status.transitionTriggerState !== "absent" ||
    !status.complete
  ) {
    throw new Error("DATABASE_RELEASE_MIGRATION_AUTH_INCOMPLETE");
  }
}

async function assertReleaseSecurityContract(
  client: PoolClient,
): Promise<void> {
  const result = await client.query<{ exact: boolean }>(
    `WITH login AS (
       SELECT * FROM pg_catalog.pg_authid
        WHERE rolname = 'meddoc_release_security'
     ), boundary AS (
       SELECT * FROM pg_catalog.pg_authid
        WHERE rolname = 'quillmd_release_security'
     )
     SELECT
       (SELECT COUNT(*) FROM login) = 1
       AND (SELECT COUNT(*) FROM boundary) = 1
       AND (SELECT rolcanlogin AND NOT rolsuper AND NOT rolcreatedb
                   AND NOT rolcreaterole AND rolinherit AND NOT rolreplication
                   AND NOT rolbypassrls AND rolconnlimit = -1
                   AND rolvaliduntil IS NULL
                   AND rolpassword LIKE 'SCRAM-SHA-256$4096:%'
              FROM login)
       AND (SELECT NOT rolcanlogin AND NOT rolsuper AND NOT rolcreatedb
                   AND NOT rolcreaterole AND NOT rolinherit
                   AND NOT rolreplication AND NOT rolbypassrls
                   AND rolconnlimit = -1 AND rolvaliduntil IS NULL
                   AND rolpassword IS NULL
              FROM boundary)
       AND (
         SELECT COUNT(*) = 1
           AND pg_catalog.bool_and(
             member_role.rolname = 'meddoc_release_security'
             AND granted_role.rolname = 'quillmd_release_security'
             AND NOT membership.admin_option
             AND membership.inherit_option
             AND NOT membership.set_option
             AND grantor_role.rolsuper
           )
           FROM pg_catalog.pg_auth_members membership
           JOIN pg_catalog.pg_roles member_role
             ON member_role.oid = membership.member
           JOIN pg_catalog.pg_roles granted_role
             ON granted_role.oid = membership.roleid
           JOIN pg_catalog.pg_roles grantor_role
             ON grantor_role.oid = membership.grantor
          WHERE (member_role.rolname IN (
                   'meddoc_release_security', 'quillmd_release_security'
                 )
             OR granted_role.rolname IN (
                   'meddoc_release_security', 'quillmd_release_security'
                 ))
       )
       AND NOT EXISTS (
         SELECT 1
           FROM pg_catalog.pg_db_role_setting setting
          WHERE setting.setrole IN (
            (SELECT oid FROM login), (SELECT oid FROM boundary)
          )
       ) AS "exact"`,
  );
  if (result.rowCount !== 1 || result.rows[0]?.exact !== true) {
    throw new Error("DATABASE_RELEASE_MIGRATION_RELEASE_SECURITY_INCOMPLETE");
  }
}

function buildCumulativeBundle(
  sources: readonly MigrationSource[],
  count: number,
): { root: string; configPath: string } {
  const root = mkdtempSync(join(tmpdir(), "quillmd-prisma-segment-"));
  chmodSync(root, 0o700);
  const bundlePackage = join(root, "packages/db");
  const bundlePrisma = join(bundlePackage, "prisma");
  const bundleMigrations = join(bundlePrisma, "migrations");
  mkdirSync(bundleMigrations, { recursive: true, mode: 0o700 });

  for (const [source, target] of [
    [
      join(packageRoot, "prisma.config.ts"),
      join(bundlePackage, "prisma.config.ts"),
    ],
    [join(prismaRoot, "schema.prisma"), join(bundlePrisma, "schema.prisma")],
    [
      join(migrationsRoot, "migration_lock.toml"),
      join(bundleMigrations, "migration_lock.toml"),
    ],
  ] as const) {
    const metadata = lstatSync(source);
    assert(metadata.isFile() && !metadata.isSymbolicLink());
    cpSync(source, target, { preserveTimestamps: false });
    assert.equal(sha256(readFileSync(target)), sha256(readFileSync(source)));
  }

  for (const migration of sources.slice(0, count)) {
    const target = join(bundleMigrations, migration.name);
    cpSync(migration.directory, target, { recursive: true });
    assert.equal(
      sha256(readFileSync(join(target, "migration.sql"))),
      migration.checksum,
    );
  }

  const nodeModules = join(repositoryRoot, "node_modules");
  const nodeModulesMetadata = lstatSync(nodeModules);
  assert(
    nodeModulesMetadata.isDirectory() && !nodeModulesMetadata.isSymbolicLink(),
  );
  symlinkSync(nodeModules, join(root, "node_modules"), "dir");
  return { root, configPath: join(bundlePackage, "prisma.config.ts") };
}

interface PrismaMigrationChildResult {
  readonly error?: Error;
  readonly status: number | null;
  readonly signal: NodeJS.Signals | null;
  readonly stdout: unknown;
  readonly stderr: unknown;
}

/**
 * Reduce a Prisma subprocess failure to a value-free operational code. Raw
 * child output can contain connection material and must never cross the
 * release-helper logging boundary.
 */
export function classifyPrismaMigrationFailure(
  result: PrismaMigrationChildResult,
): string {
  const spawnCode = (result.error as NodeJS.ErrnoException | undefined)?.code;
  if (spawnCode === "ETIMEDOUT") {
    return "DATABASE_RELEASE_MIGRATION_PRISMA_PROCESS_TIMEOUT";
  }
  if (spawnCode === "ENOBUFS") {
    return "DATABASE_RELEASE_MIGRATION_PRISMA_OUTPUT_LIMIT";
  }
  if (spawnCode === "ENOMEM") {
    return "DATABASE_RELEASE_MIGRATION_PRISMA_RESOURCE_EXHAUSTED";
  }
  if (spawnCode === "ENOENT" || spawnCode === "EACCES") {
    return "DATABASE_RELEASE_MIGRATION_PRISMA_PROCESS_START_FAILED";
  }
  if (result.signal !== null) {
    return "DATABASE_RELEASE_MIGRATION_PRISMA_PROCESS_TERMINATED";
  }

  const diagnostic = [result.stdout, result.stderr]
    .filter((value): value is string => typeof value === "string")
    .join("\n");
  if (/\bP3009\b/u.test(diagnostic)) {
    return "DATABASE_RELEASE_MIGRATION_PRISMA_LEDGER_BLOCKED";
  }
  if (
    /(?:\b55P03\b|canceling statement due to lock timeout|lock timeout)/iu.test(
      diagnostic,
    )
  ) {
    return "DATABASE_RELEASE_MIGRATION_PRISMA_LOCK_TIMEOUT";
  }
  if (
    /(?:canceling statement due to statement timeout|statement timeout)/iu.test(
      diagnostic,
    )
  ) {
    return "DATABASE_RELEASE_MIGRATION_PRISMA_STATEMENT_TIMEOUT";
  }
  if (/\bP3018\b|\b25P02\b/u.test(diagnostic)) {
    return "DATABASE_RELEASE_MIGRATION_PRISMA_APPLY_FAILED";
  }
  if (/\bP\d{4}\b/u.test(diagnostic)) {
    return "DATABASE_RELEASE_MIGRATION_PRISMA_KNOWN_ERROR";
  }
  return "DATABASE_RELEASE_MIGRATION_PRISMA_FAILED";
}

function runPrismaMigration(configPath: string, databaseUrl: string): void {
  const result = spawnSync(
    "npx",
    ["--no-install", "prisma", "migrate", "deploy", "--config", configPath],
    {
      cwd: repositoryRoot,
      encoding: "utf8",
      maxBuffer: 16 * 1024 * 1024,
      timeout: 15 * 60_000,
      env: buildPrismaMigrationChildEnvironment(databaseUrl, process.env),
    },
  );
  if (result.error || result.status !== 0 || result.signal !== null) {
    throw new Error(classifyPrismaMigrationFailure(result));
  }
}

async function main(): Promise<void> {
  let pool: Pool | null = null;
  let client: PoolClient | null = null;
  let bundleRoot: string | null = null;
  let diagnosticStage = "STARTUP";
  try {
    diagnosticStage = "ARGUMENTS";
    const phase = parsePrismaMigrationSegmentArgs(process.argv.slice(2));
    const databaseUrl = process.env.DATABASE_URL;
    if (!databaseUrl) {
      throw new Error("DATABASE_RELEASE_MIGRATION_DATABASE_URL_REQUIRED");
    }
    diagnosticStage = "SOURCE_CONTRACT";
    const probeUrl = buildMigrationProbeConnectionString({
      databaseUrl,
      phase,
      environment: process.env,
    });
    const sources = readExactMigrationSources();
    diagnosticStage = "CONNECT";
    pool = new Pool({
      connectionString: probeUrl,
      max: 3,
      connectionTimeoutMillis: 10_000,
    });
    client = await pool.connect();
    diagnosticStage = "TARGET";
    const targetProof = await proveTarget(
      client,
      databaseUrl,
      phase !== "status",
      process.env,
    );
    diagnosticStage = "LEDGER_BEFORE";
    const before = await readLedger(client, sources);
    assertExactLedgerPrefix(before, sources);

    if (phase === "status") {
      process.stdout.write(
        `${JSON.stringify({
          event: "status",
          targetFingerprints: migrationApprovalFingerprints({
            targetFingerprint: targetProof.fingerprint,
            inRecovery: targetProof.inRecovery,
            ledger: before,
            sources,
          }),
          appliedMigrations: before.length,
          lastMigration: before.at(-1)?.migrationName ?? null,
        })}\n`,
      );
      return;
    }

    const segment = PRISMA_MIGRATION_SEGMENTS[phase];
    if (
      before.length < segment.minimumApplied ||
      before.length > segment.count
    ) {
      throw new Error("DATABASE_RELEASE_MIGRATION_LEDGER_PHASE_MISMATCH");
    }
    diagnosticStage = "AUTHORIZATION";
    authorizeMutation(
      phase,
      databaseUrl,
      databaseReleaseMigrationApprovalFingerprint({
        targetFingerprint: targetProof.fingerprint,
        phase,
        ledger: before,
        sources,
      }),
    );

    if (segment.requiresLineage) {
      diagnosticStage = "LINEAGE_CONTRACT";
      await assertLineageContract(client);
    }
    if (segment.requiresAuth) {
      diagnosticStage = "AUTH_CONTRACT";
      await assertAuthContract(client);
    }
    if (segment.requiresReleaseSecurity) {
      diagnosticStage = "RELEASE_SECURITY_CONTRACT";
      await assertReleaseSecurityContract(client);
    }

    diagnosticStage = "BUNDLE";
    let migrationConfigPath: string;
    if (phase === "v9") {
      migrationConfigPath = join(packageRoot, "prisma.config.ts");
    } else {
      const bundle = buildCumulativeBundle(sources, segment.count);
      bundleRoot = bundle.root;
      migrationConfigPath = bundle.configPath;
    }
    const deployUrl = buildMigrationDeployConnectionString({
      databaseUrl,
      environment: process.env,
    });
    diagnosticStage = "PRISMA_DEPLOY";
    runPrismaMigration(migrationConfigPath, deployUrl);

    diagnosticStage = "TARGET_AFTER";
    const afterTargetProof = await proveTarget(
      client,
      databaseUrl,
      true,
      process.env,
    );
    assert.equal(afterTargetProof.fingerprint, targetProof.fingerprint);
    diagnosticStage = "LEDGER_AFTER";
    const after = await readLedger(client, sources);
    assertExactLedgerPrefix(after, sources);
    assert.equal(after.length, segment.count);
    assert.equal(after.at(-1)?.migrationName, segment.lastMigration);
    process.stdout.write("DATABASE_RELEASE_MIGRATION_PASS\n");
  } catch (error: unknown) {
    const safeCode =
      error instanceof Error &&
      /^DATABASE_RELEASE_MIGRATION_[A-Z0-9_]{2,100}$/u.test(error.message)
        ? error.message
        : `DATABASE_RELEASE_MIGRATION_FAIL_${diagnosticStage}`;
    process.stderr.write(`${safeCode}\n`);
    process.exitCode = 1;
  } finally {
    client?.release();
    if (pool) {
      try {
        await pool.end();
      } catch {
        process.exitCode = 1;
      }
    }
    if (bundleRoot) rmSync(bundleRoot, { recursive: true, force: true });
  }
}

if (process.env.VITEST !== "true") {
  void main().catch(() => {
    process.stderr.write("DATABASE_RELEASE_MIGRATION_FAIL\n");
    process.exitCode = 1;
  });
}
