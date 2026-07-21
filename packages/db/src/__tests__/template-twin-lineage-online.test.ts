import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it, vi } from "vitest";

import {
  assertExactLineageConstraintCatalog,
  assertExactLineageIndexCatalog,
  assertLineageBatchSize,
  backfillLineageBatch,
  buildLineageGuardIndex,
  LINEAGE_FINAL_INDEX,
  LINEAGE_PARTIAL_INDEX,
  LINEAGE_VALIDATION_CONSTRAINT,
  sanitizeLineageMigrationError,
  TEMPLATE_KIND_INDEX,
  type RawSqlClient,
  type TransactionalRawSqlClient,
} from "../template-twin-lineage-online";
import { acquireLineageOperatorSessionLock } from "../template-twin-lineage-session-lock";
import type { Pool } from "pg";

const ROOT = path.resolve(__dirname, "../../../..");
const EXPAND_MIGRATION = readFileSync(
  path.join(
    ROOT,
    "packages/db/prisma/migrations/20260715162000_template_twin_docx_v1/migration.sql",
  ),
  "utf8",
);
const OPERATOR = readFileSync(
  path.join(ROOT, "packages/db/src/template-twin-lineage-online.ts"),
  "utf8",
);
const GENERIC_LIFECYCLE = readFileSync(
  path.join(ROOT, "apps/transcribe-md/src/actions/note-template-lifecycle.ts"),
  "utf8",
);

function progress(overrides: Record<string, unknown> = {}) {
  return {
    operationKey: "note_templates_lineage_v1",
    phase: "GUARDED",
    lastProcessedId: null,
    rowsProcessed: 0n,
    batchCount: 0n,
    lastBatchRows: 0,
    lastErrorCode: null,
    startedAt: null,
    updatedAt: new Date("2026-07-16T00:00:00.000Z"),
    completedAt: null,
    ...overrides,
  };
}

function exactIndexRow(
  indexName: string,
  overrides: Record<string, unknown> = {},
) {
  const templateKind = indexName === TEMPLATE_KIND_INDEX;
  const partial = indexName === LINEAGE_PARTIAL_INDEX;
  const columns = templateKind
    ? ['"doctorId"', '"templateKind"', "status", ""]
    : ['"lineageId"', "version", "", ""];
  return {
    indexName,
    tableName: "note_templates",
    indexRelkind: "i",
    indexPersistence: "p",
    tableRelkind: "r",
    accessMethod: "btree",
    valid: true,
    ready: true,
    live: true,
    unique: !templateKind,
    immediate: true,
    exclusion: false,
    primary: false,
    clustered: false,
    replicaIdentity: false,
    nullsNotDistinct: false,
    keyAttributeCount: templateKind ? 3 : 2,
    attributeCount: templateKind ? 3 : 2,
    hasExpressions: false,
    hasPredicate: partial,
    hasOptions: false,
    keyColumnsExact: true,
    noConstraintDependency: true,
    predicate: partial ? '("lineageId" IS NOT NULL)' : null,
    columnOne: columns[0],
    columnTwo: columns[1],
    columnThree: columns[2],
    columnFour: columns[3],
    ...overrides,
  };
}

function exactConstraintRow(overrides: Record<string, unknown> = {}) {
  return {
    type: "c",
    validated: true,
    local: true,
    inheritCount: 0,
    parentId: "0",
    noInherit: false,
    deferrable: false,
    deferred: false,
    columnKeyExact: true,
    expression: '("lineageId" IS NOT NULL)',
    ...overrides,
  };
}

function exactTransitionTriggerRow(overrides: Record<string, unknown> = {}) {
  return {
    enabled: "O",
    triggerType: 7,
    attributeCount: 0,
    argumentCount: 0,
    arguments: "",
    functionName: "note_templates_assign_lineage_during_transition",
    functionSchema: "public",
    language: "plpgsql",
    securityDefiner: false,
    leakproof: false,
    volatility: "v",
    parallel: "u",
    functionKind: "f",
    functionArgumentCount: 0,
    returnsTrigger: true,
    functionConfig: null,
    functionSource: `BEGIN
  IF NEW."lineageId" IS NULL THEN
    NEW."lineageId" := NEW."id";
  END IF;
  RETURN NEW;
END;`,
    ...overrides,
  };
}

describe("Template Twin NoteTemplate lineage online transition", () => {
  it("keeps prisma migrate deploy expand-only for the populated table", () => {
    expect(EXPAND_MIGRATION).toContain('ADD COLUMN "lineageId" TEXT');
    expect(EXPAND_MIGRATION).toContain(
      'CREATE TABLE "template_twin_lineage_migration_progress"',
    );
    expect(EXPAND_MIGRATION).toContain(
      "note_templates_assign_lineage_during_transition",
    );
    expect(EXPAND_MIGRATION).toContain(
      "template_twin_lineage_progress_guard_update_delete",
    );
    expect(EXPAND_MIGRATION).toContain(
      "OLD.\"phase\" = 'CONTRACTED' AND NEW IS DISTINCT FROM OLD",
    );
    expect(EXPAND_MIGRATION).not.toMatch(
      /UPDATE\s+"note_templates"\s+SET\s+"lineageId"/i,
    );
    expect(EXPAND_MIGRATION).not.toMatch(
      /ALTER\s+COLUMN\s+"lineageId"\s+SET\s+NOT\s+NULL/i,
    );
    expect(EXPAND_MIGRATION).not.toMatch(
      /CREATE\s+(?:UNIQUE\s+)?INDEX[\s\S]{0,100}ON\s+"note_templates"\s*\(\s*"lineageId"/i,
    );
    // We do not rely on whether Prisma wraps a migration file: expand is an
    // explicit bounded transaction, while every CONCURRENTLY operation lives
    // in the explicit non-transactional operator.
    expect(EXPAND_MIGRATION).toMatch(/^\s*BEGIN\s*;/im);
    expect(EXPAND_MIGRATION).toContain("SET LOCAL lock_timeout = '2s'");
    expect(EXPAND_MIGRATION).toContain("SET LOCAL statement_timeout = '30s'");
    expect(EXPAND_MIGRATION.trimEnd().endsWith("COMMIT;")).toBe(true);
    expect(EXPAND_MIGRATION).not.toMatch(
      /^\s*CREATE\s+(?:UNIQUE\s+)?INDEX\s+CONCURRENTLY/im,
    );
  });

  it("builds both transition and final populated-table indexes concurrently", () => {
    expect(OPERATOR).toContain(
      'CREATE UNIQUE INDEX CONCURRENTLY "${LINEAGE_PARTIAL_INDEX}"',
    );
    expect(OPERATOR).toContain(
      'CREATE UNIQUE INDEX CONCURRENTLY "${LINEAGE_FINAL_INDEX}"',
    );
    expect(OPERATOR).toContain(
      'CREATE INDEX CONCURRENTLY "${TEMPLATE_KIND_INDEX}"',
    );
    expect(OPERATOR).toContain("DROP INDEX CONCURRENTLY");
    expect(OPERATOR).toContain(
      "LINEAGE_MIGRATION_BACKFILL_REQUIRES_GUARD_INDEX",
    );
    expect(OPERATOR).toContain("ns.nspname = 'public'");
    expect(OPERATOR).toContain("'public.\"note_templates\"'::regclass");
    expect(OPERATOR).not.toContain("current_schema()");
  });

  it("bounds batch sizes and stores only stable failure codes", () => {
    expect(assertLineageBatchSize(1)).toBe(1);
    expect(assertLineageBatchSize(10_000)).toBe(10_000);
    expect(() => assertLineageBatchSize(0)).toThrow(/BATCH_SIZE/);
    expect(() => assertLineageBatchSize(10_001)).toThrow(/BATCH_SIZE/);
    expect(sanitizeLineageMigrationError(new Error("password=secret"))).toBe(
      "UNCLASSIFIED_OPERATOR_FAILURE",
    );
    expect(
      sanitizeLineageMigrationError(
        new Error("canceling statement due to lock timeout"),
      ),
    ).toBe("LOCK_TIMEOUT");
  });

  it("refuses a batch until the independently verified guard index is valid", async () => {
    const client = {} as TransactionalRawSqlClient;
    client.$queryRawUnsafe = vi.fn(async (sql: string) => {
      if (sql.includes("migration_progress")) return [progress()];
      if (sql.includes("pg_get_indexdef")) return [];
      if (sql.includes("SELECT object.relkind::TEXT")) return [];
      throw new Error(`Unexpected SQL: ${sql}`);
    }) as RawSqlClient["$queryRawUnsafe"];
    client.$executeRawUnsafe = vi.fn().mockResolvedValue(0);
    client.$transaction = vi.fn(async (callback) => callback(client));

    await expect(backfillLineageBatch(client, 100)).rejects.toThrow(
      "LINEAGE_MIGRATION_BACKFILL_REQUIRES_GUARD_INDEX",
    );
    expect(client.$transaction).toHaveBeenCalledOnce();
  });

  it("commits a primary-key batch and durable cursor in one transaction", async () => {
    const queries: Array<{ sql: string; values: unknown[] }> = [];
    const executes: string[] = [];
    const client = {} as TransactionalRawSqlClient;
    client.$executeRawUnsafe = vi.fn(async (sql: string) => {
      executes.push(sql);
      return 0;
    });
    client.$queryRawUnsafe = vi.fn(
      async (sql: string, ...values: unknown[]) => {
        queries.push({ sql, values });
        if (sql.includes("pg_get_indexdef")) {
          return [exactIndexRow(String(values[0]))];
        }
        if (sql.includes("FROM pg_catalog.pg_trigger trigger_catalog")) {
          return [exactTransitionTriggerRow()];
        }
        if (sql.includes("FROM pg_class c")) {
          return [{ exists: true, isValid: true, isReady: true }];
        }
        if (sql.includes("pg_advisory_xact_lock")) return [{}];
        if (sql.includes("FOR UPDATE") && sql.includes("migration_progress")) {
          return [progress()];
        }
        if (sql.includes("WITH batch AS")) {
          return [{ count: 2n, lastId: "template-0002" }];
        }
        if (sql.includes('UPDATE "template_twin_lineage_migration_progress"')) {
          return [
            progress({
              phase: "BACKFILLING",
              lastProcessedId: "template-0002",
              rowsProcessed: 2n,
              batchCount: 1n,
              lastBatchRows: 2,
              startedAt: new Date("2026-07-16T00:00:00.000Z"),
            }),
          ];
        }
        throw new Error(`Unexpected SQL: ${sql}`);
      },
    ) as RawSqlClient["$queryRawUnsafe"];
    client.$transaction = vi.fn(async (callback) => callback(client));

    const result = await backfillLineageBatch(client, 2);
    expect(result).toMatchObject({
      batchRows: 2,
      rowsProcessed: 2,
      batchCount: 1,
      lastProcessedId: "template-0002",
      complete: false,
    });
    const batch = queries.find((query) => query.sql.includes("WITH batch AS"));
    expect(batch?.sql).toContain('ORDER BY n."id"');
    expect(batch?.sql).toContain("FOR UPDATE");
    expect(batch?.sql).not.toContain("SKIP LOCKED");
    expect(batch?.values).toEqual([null, 2]);
    expect(executes).toContain("SET LOCAL lock_timeout = '2s'");
    expect(executes).toContain("SET LOCAL statement_timeout = '30s'");
  });

  it("creates and catalog-verifies the partial guard outside a transaction", async () => {
    let indexExists = false;
    let currentPhase = "EXPANDED";
    const standaloneSql: string[] = [];
    const client = {} as TransactionalRawSqlClient;
    client.$executeRawUnsafe = vi.fn(
      async (sql: string, ...values: unknown[]) => {
        if (sql.includes("CREATE UNIQUE INDEX CONCURRENTLY"))
          indexExists = true;
        if (
          sql.includes('UPDATE "template_twin_lineage_migration_progress"') &&
          typeof values[1] === "string"
        ) {
          currentPhase = values[1];
        }
        if (/^CREATE UNIQUE INDEX CONCURRENTLY/m.test(sql)) {
          standaloneSql.push(sql);
        }
        return 0;
      },
    );
    client.$queryRawUnsafe = vi.fn(
      async (sql: string, ...values: unknown[]) => {
        if (sql.includes("pg_get_indexdef")) {
          return indexExists ? [exactIndexRow(String(values[0]))] : [];
        }
        if (sql.includes("SELECT object.relkind::TEXT")) return [];
        if (sql.includes("FROM pg_catalog.pg_trigger trigger_catalog")) {
          return [exactTransitionTriggerRow()];
        }
        if (sql.includes("FROM pg_class c")) {
          return [
            {
              exists: indexExists,
              isValid: indexExists,
              isReady: indexExists,
            },
          ];
        }
        if (sql.includes("pg_advisory_xact_lock")) return [{}];
        if (sql.includes("FOR UPDATE"))
          return [progress({ phase: currentPhase })];
        if (sql.includes("migration_progress")) {
          return [progress({ phase: currentPhase })];
        }
        throw new Error(`Unexpected SQL: ${sql}`);
      },
    ) as RawSqlClient["$queryRawUnsafe"];
    client.$transaction = vi.fn(async (callback) => callback(client));

    await buildLineageGuardIndex(client);
    expect(standaloneSql).toHaveLength(1);
    expect(standaloneSql[0]).toContain("CREATE UNIQUE INDEX CONCURRENTLY");
    expect(client.$transaction).not.toHaveBeenCalledWith(
      expect.any(Function),
      expect.objectContaining({ isolationLevel: expect.anything() }),
    );
  });

  it("requires the complete fixed index topology, including predicate and bounds", async () => {
    const rows = new Map([
      [LINEAGE_PARTIAL_INDEX, exactIndexRow(LINEAGE_PARTIAL_INDEX)],
      [LINEAGE_FINAL_INDEX, exactIndexRow(LINEAGE_FINAL_INDEX)],
      [TEMPLATE_KIND_INDEX, exactIndexRow(TEMPLATE_KIND_INDEX)],
    ]);
    const client = {
      $executeRawUnsafe: vi.fn(),
      $queryRawUnsafe: vi.fn(async (_sql: string, indexName: unknown) => {
        const row = rows.get(String(indexName));
        return row ? [row] : [];
      }),
    } as unknown as RawSqlClient;

    await expect(
      assertExactLineageIndexCatalog(client, LINEAGE_PARTIAL_INDEX),
    ).resolves.toBeUndefined();
    await expect(
      assertExactLineageIndexCatalog(client, LINEAGE_FINAL_INDEX),
    ).resolves.toBeUndefined();
    await expect(
      assertExactLineageIndexCatalog(client, TEMPLATE_KIND_INDEX),
    ).resolves.toBeUndefined();
    const indexContractSql = String(
      vi.mocked(client.$queryRawUnsafe).mock.calls[0]?.[0],
    );
    expect(indexContractSql).toContain("ELSE ARRAY[]::SMALLINT[]");
    expect(indexContractSql).not.toContain("ELSE FALSE");

    rows.set(
      LINEAGE_FINAL_INDEX,
      exactIndexRow(LINEAGE_FINAL_INDEX, { columnThree: "unexpected" }),
    );
    await expect(
      assertExactLineageIndexCatalog(client, LINEAGE_FINAL_INDEX),
    ).rejects.toThrow("LINEAGE_MIGRATION_INDEX_DEFINITION_MISMATCH");

    rows.set(
      LINEAGE_PARTIAL_INDEX,
      exactIndexRow(LINEAGE_PARTIAL_INDEX, { predicate: null }),
    );
    await expect(
      assertExactLineageIndexCatalog(client, LINEAGE_PARTIAL_INDEX),
    ).rejects.toThrow("LINEAGE_MIGRATION_INDEX_DEFINITION_MISMATCH");
  });

  it("requires the complete local nondeferrable lineage check contract", async () => {
    let row = exactConstraintRow();
    const client = {
      $executeRawUnsafe: vi.fn(),
      $queryRawUnsafe: vi.fn(async () => [row]),
    } as unknown as RawSqlClient;

    await expect(
      assertExactLineageConstraintCatalog(client, true),
    ).resolves.toBeUndefined();
    row = exactConstraintRow({ expression: "version IS NOT NULL" });
    await expect(
      assertExactLineageConstraintCatalog(client, true),
    ).rejects.toThrow("LINEAGE_MIGRATION_CONSTRAINT_DEFINITION_MISMATCH");
    row = exactConstraintRow({ validated: false });
    await expect(
      assertExactLineageConstraintCatalog(client, false),
    ).resolves.toBeUndefined();
    await expect(
      assertExactLineageConstraintCatalog(client, true),
    ).rejects.toThrow("LINEAGE_MIGRATION_CONSTRAINT_DEFINITION_MISMATCH");
    expect(LINEAGE_VALIDATION_CONSTRAINT).toBe(
      "note_templates_lineageId_not_null_check",
    );
  });

  it("makes generic application writes explicit and legacy reads null-tolerant", () => {
    expect(GENERIC_LIFECYCLE).toContain("lineageId: string | null");
    expect(GENERIC_LIFECYCLE).toContain(
      "const lineageId = existing?.lineageId ?? existing?.id ?? randomUUID()",
    );
    expect(GENERIC_LIFECYCLE).toContain(
      "lineageId: existing.lineageId ?? existing.id",
    );
    expect(GENERIC_LIFECYCLE).toContain("lineageId: randomUUID()");
  });

  it("keeps validation and the short NOT NULL contract as separate phases", () => {
    const addCheck = OPERATOR.indexOf(
      'CHECK ("lineageId" IS NOT NULL) NOT VALID',
    );
    const validate = OPERATOR.indexOf("VALIDATE CONSTRAINT");
    const setNotNull = OPERATOR.indexOf(
      'ALTER COLUMN "lineageId" SET NOT NULL',
    );
    expect(addCheck).toBeGreaterThanOrEqual(0);
    expect(validate).toBeGreaterThan(addCheck);
    expect(setNotNull).toBeGreaterThan(validate);
    expect(OPERATOR).toContain("SET LOCAL lock_timeout = '2s'");
  });

  it("holds and releases one session lock around standalone operator work", async () => {
    const releaseConnection = vi.fn();
    const query = vi
      .fn()
      .mockResolvedValueOnce({ rows: [{ acquired: true }] })
      .mockResolvedValueOnce({ rows: [{ released: true }] });
    const pool = {
      connect: vi.fn().mockResolvedValue({ query, release: releaseConnection }),
    } as unknown as Pool;

    const lock = await acquireLineageOperatorSessionLock(pool);
    expect(releaseConnection).not.toHaveBeenCalled();
    await lock.release();
    expect(query.mock.calls[0]?.[0]).toContain("pg_try_advisory_lock");
    expect(query.mock.calls[1]?.[0]).toContain("pg_advisory_unlock");
    expect(releaseConnection).toHaveBeenCalledOnce();
  });

  it("fails an opposing session operator without leaking its connection", async () => {
    const releaseConnection = vi.fn();
    const pool = {
      connect: vi.fn().mockResolvedValue({
        query: vi.fn().mockResolvedValue({ rows: [{ acquired: false }] }),
        release: releaseConnection,
      }),
    } as unknown as Pool;

    await expect(acquireLineageOperatorSessionLock(pool)).rejects.toThrow(
      "LINEAGE_MIGRATION_OPERATOR_BUSY",
    );
    expect(releaseConnection).toHaveBeenCalledOnce();
  });
});
