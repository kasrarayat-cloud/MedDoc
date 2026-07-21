// ============================================================================
// Template Twin NoteTemplate lineage online migration primitives
// ----------------------------------------------------------------------------
// These functions deliberately operate below Prisma's model API because the
// expand phase temporarily permits legacy NoteTemplate.lineageId NULL values
// while schema.prisma describes the final contracted (NOT NULL) shape.
//
// Safety properties:
//   * each batch is bounded and ordered by the stable NoteTemplate primary key;
//   * row changes and the durable cursor commit in the same transaction;
//   * one transaction-scoped advisory lock serializes operators;
//   * no SKIP LOCKED cursor can advance past a temporarily locked row;
//   * concurrent indexes are executed outside a transaction and independently
//     verified through pg_index before the durable phase advances;
//   * validation precedes the short ACCESS EXCLUSIVE NOT NULL contract lock.
// ============================================================================

export const LINEAGE_OPERATION_KEY = "note_templates_lineage_v1";
export const LINEAGE_ADVISORY_LOCK_KEY =
  "template_twin_note_templates_lineage_online_v1";
export const LINEAGE_PARTIAL_INDEX =
  "note_templates_lineage_version_populated_key";
export const LINEAGE_FINAL_INDEX = "note_templates_lineageId_version_key";
export const TEMPLATE_KIND_INDEX =
  "note_templates_doctorId_templateKind_status_idx";
export const LINEAGE_VALIDATION_CONSTRAINT =
  "note_templates_lineageId_not_null_check";
export const LINEAGE_PROOF_CONTRACT_VERSION = 1;

export const MIN_BATCH_SIZE = 1;
export const MAX_BATCH_SIZE = 10_000;

export type LineageMigrationPhase =
  | "EXPANDED"
  | "GUARDING"
  | "GUARDED"
  | "BACKFILLING"
  | "BACKFILLED"
  | "INDEXING"
  | "INDEXED"
  | "VALIDATING"
  | "VALIDATED"
  | "CONTRACTED"
  | "FAILED";

export interface RawSqlClient {
  $executeRawUnsafe(query: string, ...values: unknown[]): Promise<number>;
  $queryRawUnsafe<T = unknown>(query: string, ...values: unknown[]): Promise<T>;
}

export interface TransactionalRawSqlClient extends RawSqlClient {
  $transaction<T>(
    callback: (tx: RawSqlClient) => Promise<T>,
    options?: { timeout?: number; maxWait?: number },
  ): Promise<T>;
}

interface ProgressDbRow {
  operationKey: string;
  phase: LineageMigrationPhase;
  lastProcessedId: string | null;
  rowsProcessed: bigint | number | string;
  batchCount: bigint | number | string;
  lastBatchRows: number;
  lastErrorCode: string | null;
  startedAt: Date | string | null;
  updatedAt: Date | string;
  completedAt: Date | string | null;
}

interface CountDbRow {
  count: bigint | number | string;
}

interface BoolDbRow {
  value: boolean;
}

interface BatchDbRow {
  count: bigint | number | string;
  lastId: string | null;
}

interface IndexDbRow {
  exists: boolean;
  isValid: boolean;
  isReady: boolean;
}

interface ConstraintDbRow {
  exists: boolean;
  isValidated: boolean;
}

export interface LineageIndexContractRow {
  indexName: string;
  tableName: string;
  indexRelkind: string;
  indexPersistence: string;
  tableRelkind: string;
  accessMethod: string;
  valid: boolean;
  ready: boolean;
  live: boolean;
  unique: boolean;
  immediate: boolean;
  exclusion: boolean;
  primary: boolean;
  clustered: boolean;
  replicaIdentity: boolean;
  nullsNotDistinct: boolean;
  keyAttributeCount: number;
  attributeCount: number;
  hasExpressions: boolean;
  hasPredicate: boolean;
  hasOptions: boolean;
  keyColumnsExact: boolean;
  noConstraintDependency: boolean;
  predicate: string | null;
  columnOne: string | null;
  columnTwo: string | null;
  columnThree: string | null;
  columnFour: string | null;
}

export interface LineageConstraintContractRow {
  type: string;
  validated: boolean;
  local: boolean;
  inheritCount: number;
  parentId: string;
  noInherit: boolean;
  deferrable: boolean;
  deferred: boolean;
  columnKeyExact: boolean;
  expression: string;
}

interface LineageTransitionTriggerContractRow {
  enabled: string;
  triggerType: number;
  attributeCount: number;
  argumentCount: number;
  arguments: string;
  functionName: string;
  functionSchema: string;
  language: string;
  securityDefiner: boolean;
  leakproof: boolean;
  volatility: string;
  parallel: string;
  functionKind: string;
  functionArgumentCount: number;
  returnsTrigger: boolean;
  functionConfig: string[] | null;
  functionSource: string;
}

interface LineageIndexContract {
  unique: boolean;
  columns: readonly string[];
  predicate: string | null;
}

const LINEAGE_INDEX_CONTRACTS = new Map<string, LineageIndexContract>([
  [
    LINEAGE_PARTIAL_INDEX,
    {
      unique: true,
      columns: ['"lineageId"', "version"],
      predicate: '("lineageId" IS NOT NULL)',
    },
  ],
  [
    LINEAGE_FINAL_INDEX,
    {
      unique: true,
      columns: ['"lineageId"', "version"],
      predicate: null,
    },
  ],
  [
    TEMPLATE_KIND_INDEX,
    {
      unique: false,
      columns: ['"doctorId"', '"templateKind"', "status"],
      predicate: null,
    },
  ],
]);

const LINEAGE_TRANSITION_TRIGGER =
  "note_templates_assign_lineage_during_transition";
const LINEAGE_TRANSITION_FUNCTION_SOURCE = `BEGIN
  IF NEW."lineageId" IS NULL THEN
    NEW."lineageId" := NEW."id";
  END IF;
  RETURN NEW;
END;`;

export interface LineageMigrationProgress {
  operationKey: string;
  phase: LineageMigrationPhase;
  lastProcessedId: string | null;
  rowsProcessed: number;
  batchCount: number;
  lastBatchRows: number;
  lastErrorCode: string | null;
  startedAt: string | null;
  updatedAt: string;
  completedAt: string | null;
}

export interface LineageMigrationStatus extends LineageMigrationProgress {
  nullRows: number;
  duplicateLineageVersions: number;
  partialIndex: { exists: boolean; valid: boolean; ready: boolean };
  finalIndex: { exists: boolean; valid: boolean; ready: boolean };
  templateKindIndex: { exists: boolean; valid: boolean; ready: boolean };
  validationConstraint: { exists: boolean; validated: boolean };
  presentIndexesExact: boolean;
  validationConstraintExact: boolean;
  columnNotNull: boolean;
  transitionTriggerPresent: boolean;
  transitionContractExact: boolean;
}

export interface BackfillBatchResult {
  phase: LineageMigrationPhase;
  batchRows: number;
  rowsProcessed: number;
  batchCount: number;
  lastProcessedId: string | null;
  complete: boolean;
  cursorRestarted: boolean;
}

const TX_OPTIONS = { timeout: 45_000, maxWait: 10_000 } as const;

function finiteSafeNumber(
  value: bigint | number | string,
  label: string,
): number {
  const parsed = typeof value === "bigint" ? Number(value) : Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 0) {
    throw new Error(`LINEAGE_MIGRATION_INVALID_${label.toUpperCase()}`);
  }
  return parsed;
}

function iso(value: Date | string | null): string | null {
  if (value === null) return null;
  return value instanceof Date
    ? value.toISOString()
    : new Date(value).toISOString();
}

function normalizeProgress(row: ProgressDbRow): LineageMigrationProgress {
  return {
    operationKey: row.operationKey,
    phase: row.phase,
    lastProcessedId: row.lastProcessedId,
    rowsProcessed: finiteSafeNumber(row.rowsProcessed, "rows_processed"),
    batchCount: finiteSafeNumber(row.batchCount, "batch_count"),
    lastBatchRows: finiteSafeNumber(row.lastBatchRows, "last_batch_rows"),
    lastErrorCode: row.lastErrorCode,
    startedAt: iso(row.startedAt),
    updatedAt: iso(row.updatedAt)!,
    completedAt: iso(row.completedAt),
  };
}

export function assertLineageBatchSize(batchSize: number): number {
  if (
    !Number.isInteger(batchSize) ||
    batchSize < MIN_BATCH_SIZE ||
    batchSize > MAX_BATCH_SIZE
  ) {
    throw new Error(
      `LINEAGE_MIGRATION_BATCH_SIZE_MUST_BE_${MIN_BATCH_SIZE}_TO_${MAX_BATCH_SIZE}`,
    );
  }
  return batchSize;
}

async function setLocalSafetyTimeouts(tx: RawSqlClient): Promise<void> {
  await tx.$executeRawUnsafe("SET LOCAL lock_timeout = '2s'");
  await tx.$executeRawUnsafe("SET LOCAL statement_timeout = '30s'");
}

async function acquireOperatorLock(tx: RawSqlClient): Promise<void> {
  // `$queryRaw` attempts to decode PostgreSQL's void return type and Prisma's
  // pg adapter rejects it. Execute-only still blocks and holds the xact lock.
  await tx.$executeRawUnsafe(
    "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
    LINEAGE_ADVISORY_LOCK_KEY,
  );
}

async function readLockedProgress(tx: RawSqlClient): Promise<ProgressDbRow> {
  const rows = await tx.$queryRawUnsafe<ProgressDbRow[]>(
    `SELECT
       "operationKey", "phase", "lastProcessedId", "rowsProcessed",
       "batchCount", "lastBatchRows", "lastErrorCode", "startedAt",
       "updatedAt", "completedAt"
     FROM "template_twin_lineage_migration_progress"
     WHERE "operationKey" = $1
     FOR UPDATE`,
    LINEAGE_OPERATION_KEY,
  );
  const row = rows[0];
  if (!row) throw new Error("LINEAGE_MIGRATION_PROGRESS_ROW_MISSING");
  return row;
}

export async function readLineageMigrationProgress(
  client: RawSqlClient,
): Promise<LineageMigrationProgress> {
  const rows = await client.$queryRawUnsafe<ProgressDbRow[]>(
    `SELECT
       "operationKey", "phase", "lastProcessedId", "rowsProcessed",
       "batchCount", "lastBatchRows", "lastErrorCode", "startedAt",
       "updatedAt", "completedAt"
     FROM "template_twin_lineage_migration_progress"
     WHERE "operationKey" = $1`,
    LINEAGE_OPERATION_KEY,
  );
  const row = rows[0];
  if (!row) throw new Error("LINEAGE_MIGRATION_PROGRESS_ROW_MISSING");
  return normalizeProgress(row);
}

/**
 * Commit one primary-key cursor batch. There is intentionally no SKIP LOCKED:
 * advancing past a locked row would make a cursor-only resume capable of
 * permanently missing it. A lock timeout fails the batch without moving the
 * durable cursor; the operator can safely retry.
 */
export async function backfillLineageBatch(
  client: TransactionalRawSqlClient,
  requestedBatchSize: number,
): Promise<BackfillBatchResult> {
  const batchSize = assertLineageBatchSize(requestedBatchSize);

  return client.$transaction(async (tx) => {
    await setLocalSafetyTimeouts(tx);
    await acquireOperatorLock(tx);
    await tx.$executeRawUnsafe(
      `LOCK TABLE "note_templates" IN SHARE UPDATE EXCLUSIVE MODE`,
    );
    const progressRow = await readLockedProgress(tx);
    const progress = normalizeProgress(progressRow);
    if (progress.phase === "CONTRACTED") {
      await assertExactLineageContractCatalog(tx);
      return {
        phase: progress.phase,
        batchRows: 0,
        rowsProcessed: progress.rowsProcessed,
        batchCount: progress.batchCount,
        lastProcessedId: progress.lastProcessedId,
        complete: true,
        cursorRestarted: false,
      };
    }
    try {
      await assertExactLineageIndexCatalog(tx, LINEAGE_PARTIAL_INDEX);
      await assertExactLineageTransitionTrigger(tx);
    } catch {
      throw new Error("LINEAGE_MIGRATION_BACKFILL_REQUIRES_GUARD_INDEX");
    }
    if (
      ["INDEXING", "INDEXED", "VALIDATING", "VALIDATED"].includes(
        progress.phase,
      )
    ) {
      throw new Error("LINEAGE_MIGRATION_BACKFILL_PHASE_ALREADY_ADVANCED");
    }
    if (
      !["GUARDED", "BACKFILLING", "BACKFILLED", "FAILED"].includes(
        progress.phase,
      )
    ) {
      throw new Error("LINEAGE_MIGRATION_BACKFILL_PHASE_REQUIRES_GUARD");
    }

    const result = await tx.$queryRawUnsafe<BatchDbRow[]>(
      `WITH batch AS (
         SELECT n."id"
         FROM "note_templates" n
         WHERE n."lineageId" IS NULL
           AND ($1::text IS NULL OR n."id" > $1::text)
         ORDER BY n."id"
         LIMIT $2
         FOR UPDATE
       ), updated AS (
         UPDATE "note_templates" n
         SET "lineageId" = n."id"
         FROM batch
         WHERE n."id" = batch."id" AND n."lineageId" IS NULL
         RETURNING n."id"
       )
       SELECT COUNT(*)::bigint AS "count", MAX("id") AS "lastId"
       FROM updated`,
      progress.lastProcessedId,
      batchSize,
    );
    const batch = result[0];
    if (!batch) throw new Error("LINEAGE_MIGRATION_BATCH_RESULT_MISSING");
    const batchRows = finiteSafeNumber(batch.count, "batch_rows");

    if (batchRows > 0) {
      const updated = await tx.$queryRawUnsafe<ProgressDbRow[]>(
        `UPDATE "template_twin_lineage_migration_progress"
         SET "phase" = 'BACKFILLING',
             "lastProcessedId" = $2,
             "rowsProcessed" = "rowsProcessed" + $3,
             "batchCount" = "batchCount" + 1,
             "lastBatchRows" = $3,
             "lastErrorCode" = NULL,
             "startedAt" = COALESCE("startedAt", CURRENT_TIMESTAMP),
             "updatedAt" = CURRENT_TIMESTAMP
         WHERE "operationKey" = $1
         RETURNING
           "operationKey", "phase", "lastProcessedId", "rowsProcessed",
           "batchCount", "lastBatchRows", "lastErrorCode", "startedAt",
           "updatedAt", "completedAt"`,
        LINEAGE_OPERATION_KEY,
        batch.lastId,
        batchRows,
      );
      const next = normalizeProgress(updated[0]!);
      return {
        phase: next.phase,
        batchRows,
        rowsProcessed: next.rowsProcessed,
        batchCount: next.batchCount,
        lastProcessedId: next.lastProcessedId,
        complete: false,
        cursorRestarted: false,
      };
    }

    // A restart scan is defense-in-depth for a mixed-version writer that
    // inserted a NULL row behind the cursor before the transition trigger was
    // installed. Cursor + phase are reset atomically; no row is declared done.
    const remainingRows = await tx.$queryRawUnsafe<BoolDbRow[]>(
      `SELECT EXISTS (
         SELECT 1 FROM "note_templates" WHERE "lineageId" IS NULL
       ) AS "value"`,
    );
    const remaining = remainingRows[0]?.value ?? false;
    if (remaining) {
      const updated = await tx.$queryRawUnsafe<ProgressDbRow[]>(
        `UPDATE "template_twin_lineage_migration_progress"
         SET "phase" = 'BACKFILLING',
             "lastProcessedId" = NULL,
             "lastBatchRows" = 0,
             "lastErrorCode" = NULL,
             "updatedAt" = CURRENT_TIMESTAMP
         WHERE "operationKey" = $1
         RETURNING
           "operationKey", "phase", "lastProcessedId", "rowsProcessed",
           "batchCount", "lastBatchRows", "lastErrorCode", "startedAt",
           "updatedAt", "completedAt"`,
        LINEAGE_OPERATION_KEY,
      );
      const next = normalizeProgress(updated[0]!);
      return {
        phase: next.phase,
        batchRows: 0,
        rowsProcessed: next.rowsProcessed,
        batchCount: next.batchCount,
        lastProcessedId: next.lastProcessedId,
        complete: false,
        cursorRestarted: true,
      };
    }

    const updated = await tx.$queryRawUnsafe<ProgressDbRow[]>(
      `UPDATE "template_twin_lineage_migration_progress"
       SET "phase" = 'BACKFILLED',
           "lastBatchRows" = 0,
           "lastErrorCode" = NULL,
           "updatedAt" = CURRENT_TIMESTAMP
       WHERE "operationKey" = $1
       RETURNING
         "operationKey", "phase", "lastProcessedId", "rowsProcessed",
         "batchCount", "lastBatchRows", "lastErrorCode", "startedAt",
         "updatedAt", "completedAt"`,
      LINEAGE_OPERATION_KEY,
    );
    const next = normalizeProgress(updated[0]!);
    return {
      phase: next.phase,
      batchRows: 0,
      rowsProcessed: next.rowsProcessed,
      batchCount: next.batchCount,
      lastProcessedId: next.lastProcessedId,
      complete: true,
      cursorRestarted: false,
    };
  }, TX_OPTIONS);
}

export function sanitizeLineageMigrationError(error: unknown): string {
  const message = error instanceof Error ? error.message : "";
  if (/lock timeout/i.test(message)) return "LOCK_TIMEOUT";
  if (/statement timeout/i.test(message)) return "STATEMENT_TIMEOUT";
  if (/duplicate key/i.test(message)) return "DUPLICATE_LINEAGE_VERSION";
  if (/^LINEAGE_MIGRATION_[A-Z0-9_]{2,80}$/.test(message)) return message;
  const candidate =
    typeof error === "object" && error !== null && "code" in error
      ? String((error as { code?: unknown }).code ?? "")
      : "";
  if (/^[A-Z0-9_]{2,64}$/.test(candidate)) return candidate;
  return "UNCLASSIFIED_OPERATOR_FAILURE";
}

export async function recordLineageMigrationFailure(
  client: RawSqlClient,
  error: unknown,
): Promise<string> {
  const code = sanitizeLineageMigrationError(error);
  await client.$executeRawUnsafe(
    `UPDATE "template_twin_lineage_migration_progress"
     SET "phase" = CASE
           WHEN "phase" IN ('GUARDED', 'BACKFILLED', 'INDEXED', 'VALIDATED', 'CONTRACTED')
             THEN "phase"
           ELSE 'FAILED'
         END,
         "lastErrorCode" = $2,
         "lastBatchRows" = 0, "updatedAt" = CURRENT_TIMESTAMP
     WHERE "operationKey" = $1`,
    LINEAGE_OPERATION_KEY,
    code,
  );
  return code;
}

async function countNullLineages(client: RawSqlClient): Promise<number> {
  const rows = await client.$queryRawUnsafe<CountDbRow[]>(
    `SELECT COUNT(*)::bigint AS "count"
     FROM "note_templates" WHERE "lineageId" IS NULL`,
  );
  return finiteSafeNumber(rows[0]?.count ?? -1, "null_rows");
}

async function countDuplicateLineageVersions(
  client: RawSqlClient,
): Promise<number> {
  const rows = await client.$queryRawUnsafe<CountDbRow[]>(
    `SELECT COUNT(*)::bigint AS "count"
     FROM (
       SELECT "lineageId", "version"
       FROM "note_templates"
       WHERE "lineageId" IS NOT NULL
       GROUP BY "lineageId", "version"
       HAVING COUNT(*) > 1
     ) duplicates`,
  );
  return finiteSafeNumber(rows[0]?.count ?? -1, "duplicate_rows");
}

async function readIndex(
  client: RawSqlClient,
  indexName: string,
): Promise<{ exists: boolean; valid: boolean; ready: boolean }> {
  const rows = await client.$queryRawUnsafe<IndexDbRow[]>(
    `SELECT
       EXISTS (
         SELECT 1 FROM pg_class c
         JOIN pg_namespace ns ON ns.oid = c.relnamespace
         WHERE ns.nspname = 'public' AND c.relname = $1
           AND c.relkind = 'i'
       ) AS "exists",
       COALESCE((
         SELECT i.indisvalid FROM pg_index i
         JOIN pg_class c ON c.oid = i.indexrelid
         JOIN pg_namespace ns ON ns.oid = c.relnamespace
         WHERE ns.nspname = 'public' AND c.relname = $1
       ), false) AS "isValid",
       COALESCE((
         SELECT i.indisready FROM pg_index i
         JOIN pg_class c ON c.oid = i.indexrelid
         JOIN pg_namespace ns ON ns.oid = c.relnamespace
         WHERE ns.nspname = 'public' AND c.relname = $1
       ), false) AS "isReady"`,
    indexName,
  );
  const row = rows[0] ?? { exists: false, isValid: false, isReady: false };
  return { exists: row.exists, valid: row.isValid, ready: row.isReady };
}

function requiredLineageIndexContract(indexName: string): LineageIndexContract {
  const contract = LINEAGE_INDEX_CONTRACTS.get(indexName);
  if (!contract) throw new Error("LINEAGE_MIGRATION_INDEX_NAME_INEXACT");
  return contract;
}

async function readLineageIndexContract(
  client: RawSqlClient,
  indexName: string,
): Promise<LineageIndexContractRow | null> {
  requiredLineageIndexContract(indexName);
  const rows = await client.$queryRawUnsafe<LineageIndexContractRow[]>(
    `SELECT index_object.relname::TEXT AS "indexName",
            target.relname::TEXT AS "tableName",
            index_object.relkind::TEXT AS "indexRelkind",
            index_object.relpersistence::TEXT AS "indexPersistence",
            target.relkind::TEXT AS "tableRelkind",
            access_method.amname::TEXT AS "accessMethod",
            index_state.indisvalid AS "valid",
            index_state.indisready AS "ready",
            index_state.indislive AS "live",
            index_state.indisunique AS "unique",
            index_state.indimmediate AS "immediate",
            index_state.indisexclusion AS "exclusion",
            index_state.indisprimary AS "primary",
            index_state.indisclustered AS "clustered",
            index_state.indisreplident AS "replicaIdentity",
            index_state.indnullsnotdistinct AS "nullsNotDistinct",
            index_state.indnkeyatts::INTEGER AS "keyAttributeCount",
            index_state.indnatts::INTEGER AS "attributeCount",
            index_state.indexprs IS NOT NULL AS "hasExpressions",
            index_state.indpred IS NOT NULL AS "hasPredicate",
            index_object.reloptions IS NOT NULL AS "hasOptions",
            ARRAY(
              SELECT key_column.key::SMALLINT
                FROM pg_catalog.unnest(index_state.indkey)
                  WITH ORDINALITY AS key_column(key, ordinal)
               ORDER BY key_column.ordinal
            ) = CASE
              WHEN index_object.relname IN ($2, $3) THEN ARRAY[
                (SELECT attribute.attnum
                   FROM pg_catalog.pg_attribute attribute
                  WHERE attribute.attrelid = target.oid
                    AND attribute.attname = 'lineageId'
                    AND NOT attribute.attisdropped),
                (SELECT attribute.attnum
                   FROM pg_catalog.pg_attribute attribute
                  WHERE attribute.attrelid = target.oid
                    AND attribute.attname = 'version'
                    AND NOT attribute.attisdropped)
              ]::SMALLINT[]
              WHEN index_object.relname = $4 THEN ARRAY[
                (SELECT attribute.attnum
                   FROM pg_catalog.pg_attribute attribute
                  WHERE attribute.attrelid = target.oid
                    AND attribute.attname = 'doctorId'
                    AND NOT attribute.attisdropped),
                (SELECT attribute.attnum
                   FROM pg_catalog.pg_attribute attribute
                  WHERE attribute.attrelid = target.oid
                    AND attribute.attname = 'templateKind'
                    AND NOT attribute.attisdropped),
                (SELECT attribute.attnum
                   FROM pg_catalog.pg_attribute attribute
                  WHERE attribute.attrelid = target.oid
                    AND attribute.attname = 'status'
                    AND NOT attribute.attisdropped)
              ]::SMALLINT[]
              ELSE ARRAY[]::SMALLINT[]
            END AS "keyColumnsExact",
            NOT EXISTS (
              SELECT 1
                FROM pg_catalog.pg_constraint dependency
               WHERE dependency.conindid = index_state.indexrelid
            ) AS "noConstraintDependency",
            pg_catalog.pg_get_expr(
              index_state.indpred,
              index_state.indrelid
            )::TEXT AS "predicate",
            pg_catalog.pg_get_indexdef(index_state.indexrelid, 1, TRUE)
              AS "columnOne",
            pg_catalog.pg_get_indexdef(index_state.indexrelid, 2, TRUE)
              AS "columnTwo",
            pg_catalog.pg_get_indexdef(index_state.indexrelid, 3, TRUE)
              AS "columnThree",
            pg_catalog.pg_get_indexdef(index_state.indexrelid, 4, TRUE)
              AS "columnFour"
       FROM pg_catalog.pg_class index_object
       JOIN pg_catalog.pg_namespace index_namespace
         ON index_namespace.oid = index_object.relnamespace
       JOIN pg_catalog.pg_index index_state
         ON index_state.indexrelid = index_object.oid
       JOIN pg_catalog.pg_class target
         ON target.oid = index_state.indrelid
       JOIN pg_catalog.pg_namespace target_namespace
         ON target_namespace.oid = target.relnamespace
       JOIN pg_catalog.pg_am access_method
         ON access_method.oid = index_object.relam
      WHERE index_namespace.nspname = 'public'
        AND target_namespace.nspname = 'public'
        AND index_object.relkind = 'i'
        AND index_object.relname = $1`,
    indexName,
    LINEAGE_PARTIAL_INDEX,
    LINEAGE_FINAL_INDEX,
    TEMPLATE_KIND_INDEX,
  );
  if (rows.length > 1) {
    throw new Error("LINEAGE_MIGRATION_INDEX_CATALOG_AMBIGUOUS");
  }
  if (rows.length === 0) {
    const collisions = await client.$queryRawUnsafe<Array<{ kind: string }>>(
      `SELECT object.relkind::TEXT AS "kind"
         FROM pg_catalog.pg_class object
         JOIN pg_catalog.pg_namespace namespace
           ON namespace.oid = object.relnamespace
        WHERE namespace.nspname = 'public'
          AND object.relname = $1`,
      indexName,
    );
    if (collisions.length > 0) {
      throw new Error("LINEAGE_MIGRATION_INDEX_DEFINITION_MISMATCH");
    }
  }
  return rows[0] ?? null;
}

function lineageIndexContractMatches(
  row: LineageIndexContractRow,
  indexName: string,
  requireHealthy: boolean,
): boolean {
  const contract = requiredLineageIndexContract(indexName);
  const columns = [
    row.columnOne,
    row.columnTwo,
    row.columnThree,
    row.columnFour,
  ];
  const expectedColumns = [...contract.columns, "", ""].slice(0, 4);
  return (
    row.indexName === indexName &&
    row.tableName === "note_templates" &&
    row.indexRelkind === "i" &&
    row.indexPersistence === "p" &&
    row.tableRelkind === "r" &&
    row.accessMethod === "btree" &&
    (!requireHealthy || (row.valid && row.ready && row.live)) &&
    row.unique === contract.unique &&
    row.immediate &&
    !row.exclusion &&
    !row.primary &&
    !row.clustered &&
    !row.replicaIdentity &&
    !row.nullsNotDistinct &&
    row.keyAttributeCount === contract.columns.length &&
    row.attributeCount === contract.columns.length &&
    !row.hasExpressions &&
    row.hasPredicate === (contract.predicate !== null) &&
    !row.hasOptions &&
    row.keyColumnsExact &&
    row.noConstraintDependency &&
    row.predicate === contract.predicate &&
    columns.every((column, index) => column === expectedColumns[index])
  );
}

/**
 * Prove the complete fixed-name catalog contract before a lineage phase treats
 * an index as an invariant. `requireHealthy=false` is reserved for deciding
 * whether an invalid concurrent-build shell is safe to remove and retry.
 */
export async function assertExactLineageIndexCatalog(
  client: RawSqlClient,
  indexName: string,
  requireHealthy = true,
): Promise<void> {
  const row = await readLineageIndexContract(client, indexName);
  if (!row) throw new Error("LINEAGE_MIGRATION_INDEX_MISSING");
  if (!lineageIndexContractMatches(row, indexName, requireHealthy)) {
    throw new Error("LINEAGE_MIGRATION_INDEX_DEFINITION_MISMATCH");
  }
}

async function assertLineageIndexAbsent(
  client: RawSqlClient,
  indexName: string,
): Promise<void> {
  if (await readLineageIndexContract(client, indexName)) {
    throw new Error("LINEAGE_MIGRATION_UNEXPECTED_INDEX_PRESENT");
  }
}

async function readLineageConstraintContract(
  client: RawSqlClient,
): Promise<LineageConstraintContractRow | null> {
  const rows = await client.$queryRawUnsafe<LineageConstraintContractRow[]>(
    `SELECT constraint_catalog.contype::TEXT AS "type",
            constraint_catalog.convalidated AS "validated",
            constraint_catalog.conislocal AS "local",
            constraint_catalog.coninhcount::INTEGER AS "inheritCount",
            constraint_catalog.conparentid::TEXT AS "parentId",
            constraint_catalog.connoinherit AS "noInherit",
            constraint_catalog.condeferrable AS "deferrable",
            constraint_catalog.condeferred AS "deferred",
            constraint_catalog.conkey = ARRAY[
              (SELECT attribute.attnum
                 FROM pg_catalog.pg_attribute attribute
                WHERE attribute.attrelid = target.oid
                  AND attribute.attname = 'lineageId'
                  AND NOT attribute.attisdropped)
            ]::SMALLINT[] AS "columnKeyExact",
            pg_catalog.pg_get_expr(
              constraint_catalog.conbin,
              constraint_catalog.conrelid
            )::TEXT AS "expression"
       FROM pg_catalog.pg_constraint constraint_catalog
       JOIN pg_catalog.pg_class target
         ON target.oid = constraint_catalog.conrelid
       JOIN pg_catalog.pg_namespace target_namespace
         ON target_namespace.oid = target.relnamespace
      WHERE target_namespace.nspname = 'public'
        AND target.relname = 'note_templates'
        AND constraint_catalog.conname = $1`,
    LINEAGE_VALIDATION_CONSTRAINT,
  );
  if (rows.length > 1) {
    throw new Error("LINEAGE_MIGRATION_CONSTRAINT_CATALOG_AMBIGUOUS");
  }
  return rows[0] ?? null;
}

function lineageConstraintContractMatches(
  row: LineageConstraintContractRow,
  requireValidated: boolean,
): boolean {
  return (
    row.type === "c" &&
    (!requireValidated || row.validated) &&
    row.local &&
    row.inheritCount === 0 &&
    row.parentId === "0" &&
    !row.noInherit &&
    !row.deferrable &&
    !row.deferred &&
    row.columnKeyExact &&
    row.expression === '("lineageId" IS NOT NULL)'
  );
}

export async function assertExactLineageConstraintCatalog(
  client: RawSqlClient,
  requireValidated = true,
): Promise<void> {
  const row = await readLineageConstraintContract(client);
  if (!row) throw new Error("LINEAGE_MIGRATION_CONSTRAINT_MISSING");
  if (!lineageConstraintContractMatches(row, requireValidated)) {
    throw new Error("LINEAGE_MIGRATION_CONSTRAINT_DEFINITION_MISMATCH");
  }
}

async function readLineageTransitionTriggerContract(
  client: RawSqlClient,
): Promise<LineageTransitionTriggerContractRow | null> {
  const rows = await client.$queryRawUnsafe<
    LineageTransitionTriggerContractRow[]
  >(
    `SELECT trigger_catalog.tgenabled::TEXT AS "enabled",
            trigger_catalog.tgtype::INTEGER AS "triggerType",
            pg_catalog.cardinality(
              trigger_catalog.tgattr::SMALLINT[]
            )::INTEGER AS "attributeCount",
            trigger_catalog.tgnargs::INTEGER AS "argumentCount",
            pg_catalog.encode(trigger_catalog.tgargs, 'escape') AS "arguments",
            function_catalog.proname::TEXT AS "functionName",
            function_namespace.nspname::TEXT AS "functionSchema",
            language_catalog.lanname::TEXT AS "language",
            function_catalog.prosecdef AS "securityDefiner",
            function_catalog.proleakproof AS "leakproof",
            function_catalog.provolatile::TEXT AS "volatility",
            function_catalog.proparallel::TEXT AS "parallel",
            function_catalog.prokind::TEXT AS "functionKind",
            function_catalog.pronargs::INTEGER AS "functionArgumentCount",
            function_catalog.prorettype = 'pg_catalog.trigger'::regtype
              AS "returnsTrigger",
            function_catalog.proconfig AS "functionConfig",
            function_catalog.prosrc::TEXT AS "functionSource"
       FROM pg_catalog.pg_trigger trigger_catalog
       JOIN pg_catalog.pg_class target
         ON target.oid = trigger_catalog.tgrelid
       JOIN pg_catalog.pg_namespace target_namespace
         ON target_namespace.oid = target.relnamespace
       JOIN pg_catalog.pg_proc function_catalog
         ON function_catalog.oid = trigger_catalog.tgfoid
       JOIN pg_catalog.pg_namespace function_namespace
         ON function_namespace.oid = function_catalog.pronamespace
       JOIN pg_catalog.pg_language language_catalog
         ON language_catalog.oid = function_catalog.prolang
      WHERE target_namespace.nspname = 'public'
        AND target.relname = 'note_templates'
        AND trigger_catalog.tgname = $1
        AND NOT trigger_catalog.tgisinternal`,
    LINEAGE_TRANSITION_TRIGGER,
  );
  if (rows.length > 1) {
    throw new Error("LINEAGE_MIGRATION_TRANSITION_TRIGGER_AMBIGUOUS");
  }
  return rows[0] ?? null;
}

export async function assertExactLineageTransitionTrigger(
  client: RawSqlClient,
): Promise<void> {
  const row = await readLineageTransitionTriggerContract(client);
  if (!row || !lineageTransitionTriggerContractMatches(row)) {
    throw new Error("LINEAGE_MIGRATION_TRANSITION_TRIGGER_MISMATCH");
  }
}

function lineageTransitionTriggerContractMatches(
  row: LineageTransitionTriggerContractRow,
): boolean {
  return (
    row.enabled === "O" &&
    row.triggerType === 7 &&
    row.attributeCount === 0 &&
    row.argumentCount === 0 &&
    row.arguments === "" &&
    row.functionName === LINEAGE_TRANSITION_TRIGGER &&
    row.functionSchema === "public" &&
    row.language === "plpgsql" &&
    !row.securityDefiner &&
    !row.leakproof &&
    row.volatility === "v" &&
    row.parallel === "u" &&
    row.functionKind === "f" &&
    row.functionArgumentCount === 0 &&
    row.returnsTrigger &&
    row.functionConfig === null &&
    row.functionSource.trim() === LINEAGE_TRANSITION_FUNCTION_SOURCE
  );
}

async function readLineageTransitionArtifactsAbsent(
  client: RawSqlClient,
): Promise<boolean> {
  const rows = await client.$queryRawUnsafe<
    Array<{ triggerAbsent: boolean; functionAbsent: boolean }>
  >(
    `SELECT NOT EXISTS (
              SELECT 1
                FROM pg_catalog.pg_trigger trigger_catalog
               WHERE trigger_catalog.tgrelid =
                       'public."note_templates"'::regclass
                 AND trigger_catalog.tgname = $1
                 AND NOT trigger_catalog.tgisinternal
            ) AS "triggerAbsent",
            pg_catalog.to_regprocedure(
              'public.note_templates_assign_lineage_during_transition()'
            ) IS NULL AS "functionAbsent"`,
    LINEAGE_TRANSITION_TRIGGER,
  );
  if (rows.length !== 1) {
    throw new Error("LINEAGE_MIGRATION_TRANSITION_ARTIFACT_STATE_INVALID");
  }
  return rows[0]?.triggerAbsent === true && rows[0]?.functionAbsent === true;
}

async function assertLineageTransitionArtifactsAbsent(
  client: RawSqlClient,
): Promise<void> {
  if (!(await readLineageTransitionArtifactsAbsent(client))) {
    throw new Error("LINEAGE_MIGRATION_TRANSITION_ARTIFACT_REMAINS");
  }
}

async function assertContractedLineageColumn(
  client: RawSqlClient,
): Promise<void> {
  const rows = await client.$queryRawUnsafe<Array<{ notNull: boolean }>>(
    `SELECT attribute.attnotnull AS "notNull"
       FROM pg_catalog.pg_attribute attribute
      WHERE attribute.attrelid = 'public."note_templates"'::regclass
        AND attribute.attname = 'lineageId'
        AND NOT attribute.attisdropped`,
  );
  if (rows.length !== 1 || rows[0]?.notNull !== true) {
    throw new Error("LINEAGE_MIGRATION_COLUMN_NOT_CONTRACTED");
  }
}

/** Final contracted catalog proof shared by the online operator and migrator. */
export async function assertExactLineageContractCatalog(
  client: RawSqlClient,
): Promise<void> {
  const partial = await readLineageIndexContract(client, LINEAGE_PARTIAL_INDEX);
  if (partial) throw new Error("LINEAGE_MIGRATION_PARTIAL_INDEX_REMAINS");
  await assertExactLineageIndexCatalog(client, LINEAGE_FINAL_INDEX);
  await assertExactLineageIndexCatalog(client, TEMPLATE_KIND_INDEX);
  await assertExactLineageConstraintCatalog(client, true);
  await assertContractedLineageColumn(client);
  await assertLineageTransitionArtifactsAbsent(client);
}

async function readConstraint(
  client: RawSqlClient,
): Promise<{ exists: boolean; validated: boolean }> {
  const rows = await client.$queryRawUnsafe<ConstraintDbRow[]>(
    `SELECT
       EXISTS (
         SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public."note_templates"'::regclass AND conname = $1
       ) AS "exists",
       COALESCE((
         SELECT convalidated FROM pg_constraint
         WHERE conrelid = 'public."note_templates"'::regclass AND conname = $1
       ), false) AS "isValidated"`,
    LINEAGE_VALIDATION_CONSTRAINT,
  );
  const row = rows[0] ?? { exists: false, isValidated: false };
  return { exists: row.exists, validated: row.isValidated };
}

async function assertBackfillDataReady(client: RawSqlClient): Promise<void> {
  if ((await countNullLineages(client)) !== 0) {
    throw new Error("LINEAGE_MIGRATION_NULL_ROWS_REMAIN");
  }
  if ((await countDuplicateLineageVersions(client)) !== 0) {
    throw new Error("LINEAGE_MIGRATION_DUPLICATE_LINEAGE_VERSIONS");
  }
}

async function markPhase(
  client: TransactionalRawSqlClient,
  phase: LineageMigrationPhase,
  allowedCurrentPhases: readonly LineageMigrationPhase[],
): Promise<void> {
  await client.$transaction(async (tx) => {
    await setLocalSafetyTimeouts(tx);
    await acquireOperatorLock(tx);
    const current = normalizeProgress(await readLockedProgress(tx));
    if (!allowedCurrentPhases.includes(current.phase)) {
      throw new Error("LINEAGE_MIGRATION_STALE_PHASE_TRANSITION");
    }
    await tx.$executeRawUnsafe(
      `UPDATE "template_twin_lineage_migration_progress"
       SET "phase" = $2, "lastErrorCode" = NULL,
           "updatedAt" = CURRENT_TIMESTAMP
       WHERE "operationKey" = $1`,
      LINEAGE_OPERATION_KEY,
      phase,
    );
  }, TX_OPTIONS);
}

async function markPhaseAfterLockedTableProof(
  client: TransactionalRawSqlClient,
  phase: LineageMigrationPhase,
  allowedCurrentPhases: readonly LineageMigrationPhase[],
  proof: (tx: RawSqlClient) => Promise<void>,
): Promise<void> {
  await client.$transaction(async (tx) => {
    await setLocalSafetyTimeouts(tx);
    await acquireOperatorLock(tx);
    await tx.$executeRawUnsafe(
      `LOCK TABLE "note_templates" IN SHARE UPDATE EXCLUSIVE MODE`,
    );
    const current = normalizeProgress(await readLockedProgress(tx));
    if (!allowedCurrentPhases.includes(current.phase)) {
      throw new Error("LINEAGE_MIGRATION_STALE_PHASE_TRANSITION");
    }
    await proof(tx);
    await tx.$executeRawUnsafe(
      `UPDATE "template_twin_lineage_migration_progress"
       SET "phase" = $2, "lastErrorCode" = NULL,
           "updatedAt" = CURRENT_TIMESTAMP
       WHERE "operationKey" = $1`,
      LINEAGE_OPERATION_KEY,
      phase,
    );
  }, TX_OPTIONS);
}

async function ensureConcurrentIndex(
  client: RawSqlClient,
  indexName: string,
  createSql: string,
): Promise<void> {
  const existing = await readLineageIndexContract(client, indexName);
  if (existing && (!existing.valid || !existing.ready || !existing.live)) {
    // A failed CREATE INDEX CONCURRENTLY leaves an invalid shell. IF NOT EXISTS
    // would silently keep it. Prove its entire non-health topology before the
    // fixed-name artifact is eligible for removal; a wrong same-name index is
    // never modified by this operator.
    if (!lineageIndexContractMatches(existing, indexName, false)) {
      throw new Error("LINEAGE_MIGRATION_INVALID_INDEX_DEFINITION_MISMATCH");
    }
    await client.$executeRawUnsafe(
      `DROP INDEX CONCURRENTLY IF EXISTS "${indexName}"`,
    );
  }
  const afterCleanup = await readLineageIndexContract(client, indexName);
  if (!afterCleanup) await client.$executeRawUnsafe(createSql);
  await assertExactLineageIndexCatalog(client, indexName);
}

/**
 * Establish transition-safe uniqueness before any legacy row is backfilled.
 * Existing NULL rows are outside the predicate; mixed-version inserts are
 * populated by the transition trigger and are therefore covered while the
 * concurrent build runs. This phase is a deployment gate, not a Prisma
 * migration statement.
 */
export async function buildLineageGuardIndex(
  client: TransactionalRawSqlClient,
): Promise<void> {
  const progress = await readLineageMigrationProgress(client);
  if (progress.phase === "CONTRACTED") {
    await assertExactLineageContractCatalog(client);
    return;
  }
  if (progress.phase === "GUARDED") {
    await assertExactLineageIndexCatalog(client, LINEAGE_PARTIAL_INDEX);
    await assertExactLineageTransitionTrigger(client);
    return;
  }
  if (!["EXPANDED", "GUARDING", "FAILED"].includes(progress.phase)) {
    const existing = await readIndex(client, LINEAGE_PARTIAL_INDEX);
    if (existing.exists && existing.valid && existing.ready) {
      await assertExactLineageIndexCatalog(client, LINEAGE_PARTIAL_INDEX);
      await assertExactLineageTransitionTrigger(client);
      return;
    }
    throw new Error("LINEAGE_MIGRATION_GUARD_PHASE_ALREADY_ADVANCED");
  }
  await markPhase(client, "GUARDING", ["EXPANDED", "GUARDING", "FAILED"]);
  await ensureConcurrentIndex(
    client,
    LINEAGE_PARTIAL_INDEX,
    `CREATE UNIQUE INDEX CONCURRENTLY "${LINEAGE_PARTIAL_INDEX}"
       ON "note_templates"("lineageId", "version")
       WHERE "lineageId" IS NOT NULL`,
  );
  await assertExactLineageIndexCatalog(client, LINEAGE_PARTIAL_INDEX);
  await assertExactLineageTransitionTrigger(client);
  await markPhaseAfterLockedTableProof(
    client,
    "GUARDED",
    ["GUARDING"],
    async (tx) => {
      await assertExactLineageIndexCatalog(tx, LINEAGE_PARTIAL_INDEX);
      await assertExactLineageTransitionTrigger(tx);
    },
  );
}

/**
 * Build populated-table indexes without a surrounding transaction. The caller
 * must create its client with bounded lock_timeout/statement_timeout session
 * options; CREATE INDEX CONCURRENTLY is intentionally incompatible with a
 * transaction and must not be hidden inside prisma migrate deploy.
 */
export async function buildLineageIndexes(
  client: TransactionalRawSqlClient,
): Promise<void> {
  await assertBackfillDataReady(client);
  const progress = await readLineageMigrationProgress(client);
  if (progress.phase === "CONTRACTED") {
    await assertExactLineageContractCatalog(client);
    return;
  }
  if (progress.phase === "INDEXED") {
    await assertExactLineageIndexCatalog(client, LINEAGE_FINAL_INDEX);
    await assertExactLineageIndexCatalog(client, TEMPLATE_KIND_INDEX);
    await assertLineageIndexAbsent(client, LINEAGE_PARTIAL_INDEX);
    await assertExactLineageTransitionTrigger(client);
    return;
  }
  if (
    !["BACKFILLED", "FAILED", "INDEXING", "INDEXED"].includes(progress.phase)
  ) {
    throw new Error("LINEAGE_MIGRATION_INDEX_PHASE_REQUIRES_BACKFILL");
  }
  await markPhase(client, "INDEXING", ["BACKFILLED", "INDEXING", "FAILED"]);

  await ensureConcurrentIndex(
    client,
    LINEAGE_FINAL_INDEX,
    `CREATE UNIQUE INDEX CONCURRENTLY "${LINEAGE_FINAL_INDEX}"
       ON "note_templates"("lineageId", "version")`,
  );
  await ensureConcurrentIndex(
    client,
    TEMPLATE_KIND_INDEX,
    `CREATE INDEX CONCURRENTLY "${TEMPLATE_KIND_INDEX}"
       ON "note_templates"("doctorId", "templateKind", "status")`,
  );

  await assertExactLineageIndexCatalog(client, LINEAGE_FINAL_INDEX);
  await assertExactLineageIndexCatalog(client, TEMPLATE_KIND_INDEX);

  // Full uniqueness is valid before the transition-only partial guard leaves.
  const partial = await readLineageIndexContract(client, LINEAGE_PARTIAL_INDEX);
  if (partial) {
    if (!lineageIndexContractMatches(partial, LINEAGE_PARTIAL_INDEX, true)) {
      throw new Error("LINEAGE_MIGRATION_INDEX_DEFINITION_MISMATCH");
    }
    await client.$executeRawUnsafe(
      `DROP INDEX CONCURRENTLY IF EXISTS "${LINEAGE_PARTIAL_INDEX}"`,
    );
  }
  await markPhaseAfterLockedTableProof(
    client,
    "INDEXED",
    ["INDEXING"],
    async (tx) => {
      await assertExactLineageIndexCatalog(tx, LINEAGE_FINAL_INDEX);
      await assertExactLineageIndexCatalog(tx, TEMPLATE_KIND_INDEX);
      await assertLineageIndexAbsent(tx, LINEAGE_PARTIAL_INDEX);
      await assertExactLineageTransitionTrigger(tx);
    },
  );
}

export async function validateLineageContract(
  client: TransactionalRawSqlClient,
): Promise<void> {
  await assertBackfillDataReady(client);
  const progress = await readLineageMigrationProgress(client);
  if (progress.phase === "CONTRACTED") {
    await assertExactLineageContractCatalog(client);
    return;
  }
  if (progress.phase === "VALIDATED") {
    await assertExactLineageIndexCatalog(client, LINEAGE_FINAL_INDEX);
    await assertExactLineageIndexCatalog(client, TEMPLATE_KIND_INDEX);
    await assertLineageIndexAbsent(client, LINEAGE_PARTIAL_INDEX);
    await assertExactLineageConstraintCatalog(client, true);
    await assertExactLineageTransitionTrigger(client);
    return;
  }
  if (!["INDEXED", "VALIDATING", "FAILED"].includes(progress.phase)) {
    throw new Error("LINEAGE_MIGRATION_VALIDATION_PHASE_REQUIRES_INDEXES");
  }
  await markPhase(client, "VALIDATING", ["INDEXED", "VALIDATING", "FAILED"]);

  await client.$transaction(async (tx) => {
    await setLocalSafetyTimeouts(tx);
    await acquireOperatorLock(tx);
    await tx.$executeRawUnsafe(
      `LOCK TABLE "note_templates" IN SHARE UPDATE EXCLUSIVE MODE`,
    );
    const lockedProgress = normalizeProgress(await readLockedProgress(tx));
    if (lockedProgress.phase !== "VALIDATING") {
      throw new Error("LINEAGE_MIGRATION_VALIDATION_PHASE_REQUIRES_INDEXES");
    }
    try {
      await assertExactLineageIndexCatalog(tx, LINEAGE_FINAL_INDEX);
      await assertExactLineageIndexCatalog(tx, TEMPLATE_KIND_INDEX);
      await assertLineageIndexAbsent(tx, LINEAGE_PARTIAL_INDEX);
      await assertExactLineageTransitionTrigger(tx);
    } catch {
      throw new Error("LINEAGE_MIGRATION_VALIDATION_REQUIRES_VALID_INDEXES");
    }

    const current = await readConstraint(tx);
    if (current.exists) {
      await assertExactLineageConstraintCatalog(tx, false);
    } else {
      await tx.$executeRawUnsafe(
        `ALTER TABLE "note_templates"
         ADD CONSTRAINT "${LINEAGE_VALIDATION_CONSTRAINT}"
         CHECK ("lineageId" IS NOT NULL) NOT VALID`,
      );
      await assertExactLineageConstraintCatalog(tx, false);
    }

    const beforeValidation = await readConstraint(tx);
    if (!beforeValidation.validated) {
      await tx.$executeRawUnsafe(
        `ALTER TABLE "note_templates"
         VALIDATE CONSTRAINT "${LINEAGE_VALIDATION_CONSTRAINT}"`,
      );
    }
    await assertExactLineageConstraintCatalog(tx, true);
    await tx.$executeRawUnsafe(
      `UPDATE "template_twin_lineage_migration_progress"
       SET "phase" = 'VALIDATED', "lastErrorCode" = NULL,
           "updatedAt" = CURRENT_TIMESTAMP
       WHERE "operationKey" = $1`,
      LINEAGE_OPERATION_KEY,
    );
  }, TX_OPTIONS);
}

/**
 * Linearization point for the schema transition: the transaction commit after
 * SET NOT NULL, transition-trigger removal, and progress=CONTRACTED. A bounded
 * lock timeout makes contention fail closed; rerunning after the blocker is
 * removed is idempotent.
 */
export async function contractLineageNotNull(
  client: TransactionalRawSqlClient,
): Promise<void> {
  await client.$transaction(async (tx) => {
    await setLocalSafetyTimeouts(tx);
    await acquireOperatorLock(tx);
    await tx.$executeRawUnsafe(
      `LOCK TABLE "note_templates" IN ACCESS EXCLUSIVE MODE`,
    );
    const progress = normalizeProgress(await readLockedProgress(tx));
    if (progress.phase === "CONTRACTED") {
      await assertExactLineageContractCatalog(tx);
      return;
    }
    if (progress.phase !== "VALIDATED") {
      throw new Error("LINEAGE_MIGRATION_CONTRACT_REQUIRES_VALIDATION");
    }

    // Hold the same ACCESS EXCLUSIVE lock needed by SET NOT NULL while proving
    // every fixed-name catalog object. This closes the check/use gap against
    // concurrent DDL without extending the lock across a table scan: the exact
    // validated CHECK constraint is PostgreSQL's proof that no legacy NULL is
    // present and also rejects new NULL writes.
    try {
      await assertExactLineageIndexCatalog(tx, LINEAGE_FINAL_INDEX);
      await assertExactLineageIndexCatalog(tx, TEMPLATE_KIND_INDEX);
      await assertExactLineageConstraintCatalog(tx, true);
      await assertExactLineageTransitionTrigger(tx);
    } catch {
      throw new Error("LINEAGE_MIGRATION_CONTRACT_PROOF_INCOMPLETE");
    }

    // PostgreSQL can use the already-validated CHECK proof and avoid a second
    // table scan. ALTER COLUMN still needs a short ACCESS EXCLUSIVE lock.
    await tx.$executeRawUnsafe(
      `ALTER TABLE "note_templates" ALTER COLUMN "lineageId" SET NOT NULL`,
    );
    await tx.$executeRawUnsafe(
      `DROP TRIGGER note_templates_assign_lineage_during_transition
       ON "note_templates"`,
    );
    await tx.$executeRawUnsafe(
      `DROP FUNCTION note_templates_assign_lineage_during_transition()`,
    );
    await assertExactLineageContractCatalog(tx);
    await tx.$executeRawUnsafe(
      `UPDATE "template_twin_lineage_migration_progress"
       SET "phase" = 'CONTRACTED', "lastErrorCode" = NULL,
           "updatedAt" = CURRENT_TIMESTAMP,
           "completedAt" = CURRENT_TIMESTAMP
       WHERE "operationKey" = $1`,
      LINEAGE_OPERATION_KEY,
    );
  }, TX_OPTIONS);
}

export async function readLineageMigrationStatus(
  client: RawSqlClient,
): Promise<LineageMigrationStatus> {
  const [
    progress,
    nullRows,
    duplicates,
    partialIndex,
    finalIndex,
    templateKindIndex,
    constraint,
    partialContract,
    finalContract,
    templateKindContract,
    constraintContract,
    transitionContract,
    transitionArtifactsAbsent,
  ] = await Promise.all([
    readLineageMigrationProgress(client),
    countNullLineages(client),
    countDuplicateLineageVersions(client),
    readIndex(client, LINEAGE_PARTIAL_INDEX),
    readIndex(client, LINEAGE_FINAL_INDEX),
    readIndex(client, TEMPLATE_KIND_INDEX),
    readConstraint(client),
    readLineageIndexContract(client, LINEAGE_PARTIAL_INDEX),
    readLineageIndexContract(client, LINEAGE_FINAL_INDEX),
    readLineageIndexContract(client, TEMPLATE_KIND_INDEX),
    readLineageConstraintContract(client),
    readLineageTransitionTriggerContract(client),
    readLineageTransitionArtifactsAbsent(client),
  ]);
  const columnRows = await client.$queryRawUnsafe<
    Array<{ isNotNull: boolean; transitionTriggerPresent: boolean }>
  >(
    `SELECT
       a.attnotnull AS "isNotNull",
       EXISTS (
         SELECT 1 FROM pg_trigger t
         WHERE t.tgrelid = 'public."note_templates"'::regclass
           AND t.tgname = 'note_templates_assign_lineage_during_transition'
           AND NOT t.tgisinternal
       ) AS "transitionTriggerPresent"
     FROM pg_attribute a
     WHERE a.attrelid = 'public."note_templates"'::regclass
       AND a.attname = 'lineageId' AND NOT a.attisdropped`,
  );
  const column = columnRows[0];
  if (!column) throw new Error("LINEAGE_MIGRATION_COLUMN_MISSING");

  return {
    ...progress,
    nullRows,
    duplicateLineageVersions: duplicates,
    partialIndex,
    finalIndex,
    templateKindIndex,
    validationConstraint: constraint,
    presentIndexesExact: [
      [partialContract, LINEAGE_PARTIAL_INDEX],
      [finalContract, LINEAGE_FINAL_INDEX],
      [templateKindContract, TEMPLATE_KIND_INDEX],
    ].every(
      ([row, indexName]) =>
        row === null ||
        lineageIndexContractMatches(
          row as LineageIndexContractRow,
          indexName as string,
          true,
        ),
    ),
    validationConstraintExact:
      constraintContract === null ||
      lineageConstraintContractMatches(constraintContract, false),
    columnNotNull: column.isNotNull,
    transitionTriggerPresent: column.transitionTriggerPresent,
    transitionContractExact:
      transitionContract === null
        ? transitionArtifactsAbsent
        : lineageTransitionTriggerContractMatches(transitionContract),
  };
}

/** Read one coherent status snapshot even while an operator phase is active. */
export async function readLineageMigrationStatusSnapshot(
  client: TransactionalRawSqlClient,
): Promise<LineageMigrationStatus> {
  return client.$transaction(async (tx) => {
    await tx.$executeRawUnsafe(
      "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
    );
    return readLineageMigrationStatus(tx);
  }, TX_OPTIONS);
}
