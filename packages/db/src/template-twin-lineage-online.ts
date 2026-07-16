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
  $queryRawUnsafe<T = unknown>(
    query: string,
    ...values: unknown[]
  ): Promise<T>;
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
  columnNotNull: boolean;
  transitionTriggerPresent: boolean;
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

function finiteSafeNumber(value: bigint | number | string, label: string): number {
  const parsed = typeof value === "bigint" ? Number(value) : Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 0) {
    throw new Error(`LINEAGE_MIGRATION_INVALID_${label.toUpperCase()}`);
  }
  return parsed;
}

function iso(value: Date | string | null): string | null {
  if (value === null) return null;
  return value instanceof Date ? value.toISOString() : new Date(value).toISOString();
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
  const guardIndex = await readIndex(client, LINEAGE_PARTIAL_INDEX);
  if (!guardIndex.exists || !guardIndex.valid || !guardIndex.ready) {
    throw new Error("LINEAGE_MIGRATION_BACKFILL_REQUIRES_GUARD_INDEX");
  }

  return client.$transaction(async (tx) => {
    await setLocalSafetyTimeouts(tx);
    await acquireOperatorLock(tx);
    const progressRow = await readLockedProgress(tx);
    const progress = normalizeProgress(progressRow);

    if (progress.phase === "CONTRACTED") {
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
    if (["INDEXING", "INDEXED", "VALIDATING", "VALIDATED"].includes(progress.phase)) {
      throw new Error("LINEAGE_MIGRATION_BACKFILL_PHASE_ALREADY_ADVANCED");
    }
    if (!["GUARDED", "BACKFILLING", "BACKFILLED", "FAILED"].includes(progress.phase)) {
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

async function countDuplicateLineageVersions(client: RawSqlClient): Promise<number> {
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
         WHERE ns.nspname = current_schema() AND c.relname = $1
           AND c.relkind = 'i'
       ) AS "exists",
       COALESCE((
         SELECT i.indisvalid FROM pg_index i
         JOIN pg_class c ON c.oid = i.indexrelid
         JOIN pg_namespace ns ON ns.oid = c.relnamespace
         WHERE ns.nspname = current_schema() AND c.relname = $1
       ), false) AS "isValid",
       COALESCE((
         SELECT i.indisready FROM pg_index i
         JOIN pg_class c ON c.oid = i.indexrelid
         JOIN pg_namespace ns ON ns.oid = c.relnamespace
         WHERE ns.nspname = current_schema() AND c.relname = $1
       ), false) AS "isReady"`,
    indexName,
  );
  const row = rows[0] ?? { exists: false, isValid: false, isReady: false };
  return { exists: row.exists, valid: row.isValid, ready: row.isReady };
}

async function readConstraint(
  client: RawSqlClient,
): Promise<{ exists: boolean; validated: boolean }> {
  const rows = await client.$queryRawUnsafe<ConstraintDbRow[]>(
    `SELECT
       EXISTS (
         SELECT 1 FROM pg_constraint
         WHERE conrelid = '"note_templates"'::regclass AND conname = $1
       ) AS "exists",
       COALESCE((
         SELECT convalidated FROM pg_constraint
         WHERE conrelid = '"note_templates"'::regclass AND conname = $1
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
): Promise<void> {
  await client.$transaction(async (tx) => {
    await setLocalSafetyTimeouts(tx);
    await acquireOperatorLock(tx);
    await readLockedProgress(tx);
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
  const existing = await readIndex(client, indexName);
  if (existing.exists && (!existing.valid || !existing.ready)) {
    // A failed CREATE INDEX CONCURRENTLY leaves an invalid shell. IF NOT EXISTS
    // would silently keep it, so remove only that fixed-name invalid artifact.
    await client.$executeRawUnsafe(`DROP INDEX CONCURRENTLY IF EXISTS "${indexName}"`);
  }
  const afterCleanup = await readIndex(client, indexName);
  if (!afterCleanup.exists) await client.$executeRawUnsafe(createSql);
  const verified = await readIndex(client, indexName);
  if (!verified.exists || !verified.valid || !verified.ready) {
    throw new Error(`LINEAGE_MIGRATION_INDEX_NOT_VALID_${indexName}`);
  }
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
  if (progress.phase === "CONTRACTED") return;
  if (!["EXPANDED", "GUARDING", "GUARDED", "FAILED"].includes(progress.phase)) {
    const existing = await readIndex(client, LINEAGE_PARTIAL_INDEX);
    if (existing.exists && existing.valid && existing.ready) return;
    throw new Error("LINEAGE_MIGRATION_GUARD_PHASE_ALREADY_ADVANCED");
  }
  await markPhase(client, "GUARDING");
  await ensureConcurrentIndex(
    client,
    LINEAGE_PARTIAL_INDEX,
    `CREATE UNIQUE INDEX CONCURRENTLY "${LINEAGE_PARTIAL_INDEX}"
       ON "note_templates"("lineageId", "version")
       WHERE "lineageId" IS NOT NULL`,
  );
  await markPhase(client, "GUARDED");
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
  if (progress.phase === "CONTRACTED") return;
  if (!["BACKFILLED", "FAILED", "INDEXING", "INDEXED"].includes(progress.phase)) {
    throw new Error("LINEAGE_MIGRATION_INDEX_PHASE_REQUIRES_BACKFILL");
  }
  await markPhase(client, "INDEXING");

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

  // Full uniqueness is valid before the transition-only partial guard leaves.
  await client.$executeRawUnsafe(
    `DROP INDEX CONCURRENTLY IF EXISTS "${LINEAGE_PARTIAL_INDEX}"`,
  );
  await markPhase(client, "INDEXED");
}

export async function validateLineageContract(
  client: TransactionalRawSqlClient,
): Promise<void> {
  await assertBackfillDataReady(client);
  const finalIndex = await readIndex(client, LINEAGE_FINAL_INDEX);
  const templateKindIndex = await readIndex(client, TEMPLATE_KIND_INDEX);
  if (!finalIndex.valid || !templateKindIndex.valid) {
    throw new Error("LINEAGE_MIGRATION_VALIDATION_REQUIRES_VALID_INDEXES");
  }
  const progress = await readLineageMigrationProgress(client);
  if (progress.phase === "CONTRACTED" || progress.phase === "VALIDATED") return;
  if (!["INDEXED", "VALIDATING", "FAILED"].includes(progress.phase)) {
    throw new Error("LINEAGE_MIGRATION_VALIDATION_PHASE_REQUIRES_INDEXES");
  }
  await markPhase(client, "VALIDATING");

  const current = await readConstraint(client);
  if (!current.exists) {
    await client.$transaction(async (tx) => {
      await setLocalSafetyTimeouts(tx);
      await acquireOperatorLock(tx);
      await tx.$executeRawUnsafe(
        `ALTER TABLE "note_templates"
         ADD CONSTRAINT "${LINEAGE_VALIDATION_CONSTRAINT}"
         CHECK ("lineageId" IS NOT NULL) NOT VALID`,
      );
    }, TX_OPTIONS);
  }

  const beforeValidation = await readConstraint(client);
  if (!beforeValidation.validated) {
    await client.$executeRawUnsafe(
      `ALTER TABLE "note_templates"
       VALIDATE CONSTRAINT "${LINEAGE_VALIDATION_CONSTRAINT}"`,
    );
  }
  const verified = await readConstraint(client);
  if (!verified.exists || !verified.validated) {
    throw new Error("LINEAGE_MIGRATION_CONSTRAINT_NOT_VALIDATED");
  }
  await assertBackfillDataReady(client);
  await markPhase(client, "VALIDATED");
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
    const progress = normalizeProgress(await readLockedProgress(tx));
    if (progress.phase === "CONTRACTED") return;
    if (progress.phase !== "VALIDATED") {
      throw new Error("LINEAGE_MIGRATION_CONTRACT_REQUIRES_VALIDATION");
    }

    const nullRows = await tx.$queryRawUnsafe<CountDbRow[]>(
      `SELECT COUNT(*)::bigint AS "count"
       FROM "note_templates" WHERE "lineageId" IS NULL`,
    );
    if (finiteSafeNumber(nullRows[0]?.count ?? -1, "null_rows") !== 0) {
      throw new Error("LINEAGE_MIGRATION_NULL_ROWS_REMAIN");
    }
    const constraint = await readConstraint(tx);
    const finalIndex = await readIndex(tx, LINEAGE_FINAL_INDEX);
    if (!constraint.exists || !constraint.validated || !finalIndex.valid) {
      throw new Error("LINEAGE_MIGRATION_CONTRACT_PROOF_INCOMPLETE");
    }

    // PostgreSQL can use the already-validated CHECK proof and avoid a second
    // table scan. ALTER COLUMN still needs a short ACCESS EXCLUSIVE lock.
    await tx.$executeRawUnsafe(
      `ALTER TABLE "note_templates" ALTER COLUMN "lineageId" SET NOT NULL`,
    );
    await tx.$executeRawUnsafe(
      `DROP TRIGGER IF EXISTS note_templates_assign_lineage_during_transition
       ON "note_templates"`,
    );
    await tx.$executeRawUnsafe(
      `DROP FUNCTION IF EXISTS note_templates_assign_lineage_during_transition()`,
    );
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
  const [progress, nullRows, duplicates, partialIndex, finalIndex, templateKindIndex, constraint] =
    await Promise.all([
      readLineageMigrationProgress(client),
      countNullLineages(client),
      countDuplicateLineageVersions(client),
      readIndex(client, LINEAGE_PARTIAL_INDEX),
      readIndex(client, LINEAGE_FINAL_INDEX),
      readIndex(client, TEMPLATE_KIND_INDEX),
      readConstraint(client),
    ]);
  const columnRows = await client.$queryRawUnsafe<
    Array<{ isNotNull: boolean; transitionTriggerPresent: boolean }>
  >(
    `SELECT
       a.attnotnull AS "isNotNull",
       EXISTS (
         SELECT 1 FROM pg_trigger t
         WHERE t.tgrelid = '"note_templates"'::regclass
           AND t.tgname = 'note_templates_assign_lineage_during_transition'
           AND NOT t.tgisinternal
       ) AS "transitionTriggerPresent"
     FROM pg_attribute a
     WHERE a.attrelid = '"note_templates"'::regclass
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
    columnNotNull: column.isNotNull,
    transitionTriggerPresent: column.transitionTriggerPresent,
  };
}
