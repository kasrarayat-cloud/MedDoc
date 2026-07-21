import type { PoolClient, QueryResultRow } from "pg";

export const AUTH_TOKEN_INDEX =
  "auth_tokens_one_unused_per_user_purpose" as const;
export const AUTH_TOKEN_TRANSITION_TRIGGER =
  "aaa_auth_tokens_one_unused_transition" as const;
export const AUTH_TOKEN_TRANSITION_FUNCTION =
  "auth_tokens_guard_one_unused_transition" as const;

export interface AuthTokenLinearizationStatus {
  duplicateGroups: number;
  indexExists: boolean;
  indexValid: boolean;
  indexReady: boolean;
  indexExact: boolean;
  transitionTriggerEnabled: boolean;
  transitionTriggerState: "absent" | "exact" | "mismatch";
  complete: boolean;
}

interface IndexRow extends QueryResultRow {
  exists: boolean;
  isValid: boolean;
  isReady: boolean;
  isLive: boolean;
  isUnique: boolean;
  keyAttributeCount: number;
  attributeCount: number;
  accessMethod: string;
  hasExpressions: boolean;
  nullsNotDistinct: boolean;
  definition: string;
  tableName: string | null;
  columnOne: string | null;
  columnTwo: string | null;
  predicate: string | null;
}

interface TriggerRow extends QueryResultRow {
  triggerType: number;
  triggerColumns: string[];
  triggerEnabled: string;
  internal: boolean;
  constraintOid: string;
  deferrable: boolean;
  initiallyDeferred: boolean;
  parentOid: string;
  hasQualifier: boolean;
  argumentCount: number;
  functionName: string;
  functionNamespace: string;
  functionLanguage: string;
  returnsTrigger: boolean;
  functionOwnerMatchesTable: boolean;
  securityDefiner: boolean;
  volatility: string;
  argumentCountFunction: number;
  functionConfig: string[] | null;
  functionSource: string;
  publicCanExecute: boolean;
}

const EXPECTED_INDEX_DEFINITION =
  'CREATE UNIQUE INDEX auth_tokens_one_unused_per_user_purpose ON public.auth_tokens USING btree ("userId", purpose) WHERE ("usedAt" IS NULL)';

export const AUTH_TOKEN_EXPECTED_TRANSITION_FUNCTION_SOURCE = `
BEGIN
  IF NEW."usedAt" IS NULL THEN
    -- At REPEATABLE READ/SERIALIZABLE, a transaction that began before an
    -- opposing writer committed can retain a stale snapshot after waiting on
    -- the advisory lock. Until the final unique index is valid, fail closed
    -- unless PostgreSQL can take the fresh per-command READ COMMITTED snapshot
    -- used by the post-lock existence check.
    IF current_setting('transaction_isolation') <> 'read committed' THEN
      RAISE EXCEPTION USING
        ERRCODE = '25000',
        MESSAGE = 'Unused authentication-token writes require read committed isolation during online linearization';
    END IF;
    -- Serialize every writer for the exact authority key while the concurrent
    -- index is absent. The fixed salt separates this lock namespace from
    -- application and migration locks elsewhere in the release.
    PERFORM pg_advisory_xact_lock(hashtextextended(
      NEW."userId" || E'\\x1f' || NEW."purpose"::TEXT,
      2026072015
    ));
    IF EXISTS (
      SELECT 1
      FROM public."auth_tokens" current_token
      WHERE current_token."userId" = NEW."userId"
        AND current_token."purpose" = NEW."purpose"
        AND current_token."usedAt" IS NULL
        AND current_token."id" IS DISTINCT FROM NEW."id"
    ) THEN
      RAISE EXCEPTION USING
        ERRCODE = '23505',
        CONSTRAINT = 'auth_tokens_one_unused_per_user_purpose',
        MESSAGE = 'Only one unused authentication token is permitted';
    END IF;
  END IF;
  RETURN NEW;
END;
`;

function canonicalSql(value: string): string {
  return value.replace(/\s+/gu, " ").trim();
}

function safeCount(value: string | undefined, code: string): number {
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 0) throw new Error(code);
  return parsed;
}

function predicateIsExact(predicate: string | null): boolean {
  if (!predicate) return false;
  return predicate.replace(/[\s()"]+/gu, "").toLowerCase() === "usedatisnull";
}

async function readIndex(client: PoolClient): Promise<{
  exists: boolean;
  valid: boolean;
  ready: boolean;
  live: boolean;
  exact: boolean;
}> {
  const result = await client.query<IndexRow>(
    `SELECT TRUE AS "exists", index_state.indisvalid AS "isValid",
            index_state.indisready AS "isReady",
            index_state.indislive AS "isLive",
            index_state.indisunique AS "isUnique",
            index_state.indnkeyatts::integer AS "keyAttributeCount",
            index_state.indnatts::integer AS "attributeCount",
            access_method.amname::text AS "accessMethod",
            (index_state.indexprs IS NOT NULL) AS "hasExpressions",
            index_state.indnullsnotdistinct AS "nullsNotDistinct",
            pg_get_indexdef(index_state.indexrelid) AS "definition",
            target.relname::text AS "tableName",
            pg_get_indexdef(index_state.indexrelid, 1, TRUE) AS "columnOne",
            pg_get_indexdef(index_state.indexrelid, 2, TRUE) AS "columnTwo",
            pg_get_expr(index_state.indpred, index_state.indrelid)
              AS "predicate"
       FROM pg_catalog.pg_class index_object
       JOIN pg_catalog.pg_namespace index_namespace
         ON index_namespace.oid = index_object.relnamespace
       JOIN pg_catalog.pg_index index_state
         ON index_state.indexrelid = index_object.oid
       JOIN pg_catalog.pg_class target
         ON target.oid = index_state.indrelid
       JOIN pg_catalog.pg_am access_method
         ON access_method.oid = index_object.relam
      WHERE index_namespace.nspname = 'public'
        AND index_object.relname = $1`,
    [AUTH_TOKEN_INDEX],
  );
  if (result.rowCount === 0) {
    return {
      exists: false,
      valid: false,
      ready: false,
      live: false,
      exact: false,
    };
  }
  if (result.rowCount !== 1) {
    throw new Error("AUTH_TOKEN_INDEX_CATALOG_AMBIGUOUS");
  }
  const row = result.rows[0]!;
  const exact =
    row.isUnique &&
    row.keyAttributeCount === 2 &&
    row.attributeCount === 2 &&
    row.accessMethod === "btree" &&
    !row.hasExpressions &&
    !row.nullsNotDistinct &&
    canonicalSql(row.definition) === EXPECTED_INDEX_DEFINITION &&
    row.tableName === "auth_tokens" &&
    row.columnOne === '"userId"' &&
    row.columnTwo === "purpose" &&
    predicateIsExact(row.predicate);
  return {
    exists: row.exists,
    valid: row.isValid,
    ready: row.isReady,
    live: row.isLive,
    exact,
  };
}

async function readTransitionTriggerState(
  client: PoolClient,
): Promise<"absent" | "exact" | "mismatch"> {
  const result = await client.query<TriggerRow>(
    `SELECT trigger_state.tgtype::integer AS "triggerType",
            ARRAY(
              SELECT attribute.attname::text
              FROM unnest(trigger_state.tgattr::smallint[])
                WITH ORDINALITY listed(attnum, ordinal)
              JOIN pg_catalog.pg_attribute attribute
                ON attribute.attrelid = trigger_state.tgrelid
               AND attribute.attnum = listed.attnum
              ORDER BY listed.ordinal
            ) AS "triggerColumns",
            trigger_state.tgenabled::text AS "triggerEnabled",
            trigger_state.tgisinternal AS "internal",
            trigger_state.tgconstraint::text AS "constraintOid",
            trigger_state.tgdeferrable AS "deferrable",
            trigger_state.tginitdeferred AS "initiallyDeferred",
            trigger_state.tgparentid::text AS "parentOid",
            (trigger_state.tgqual IS NOT NULL) AS "hasQualifier",
            trigger_state.tgnargs::integer AS "argumentCount",
            trigger_function.proname::text AS "functionName",
            function_namespace.nspname::text AS "functionNamespace",
            function_language.lanname::text AS "functionLanguage",
            (trigger_function.prorettype =
              'pg_catalog.trigger'::pg_catalog.regtype) AS "returnsTrigger",
            (trigger_function.proowner = target.relowner)
              AS "functionOwnerMatchesTable",
            trigger_function.prosecdef AS "securityDefiner",
            trigger_function.provolatile::text AS "volatility",
            trigger_function.pronargs::integer AS "argumentCountFunction",
            trigger_function.proconfig AS "functionConfig",
            trigger_function.prosrc AS "functionSource",
            EXISTS (
              SELECT 1
              FROM pg_catalog.aclexplode(COALESCE(
                trigger_function.proacl,
                pg_catalog.acldefault(
                  'f'::"char", trigger_function.proowner
                )
              )) function_privilege
              WHERE function_privilege.grantee = 0
                AND function_privilege.privilege_type = 'EXECUTE'
            ) AS "publicCanExecute"
       FROM pg_catalog.pg_trigger trigger_state
       JOIN pg_catalog.pg_class target
         ON target.oid = trigger_state.tgrelid
       JOIN pg_catalog.pg_namespace target_namespace
         ON target_namespace.oid = target.relnamespace
       JOIN pg_catalog.pg_proc trigger_function
         ON trigger_function.oid = trigger_state.tgfoid
       JOIN pg_catalog.pg_namespace function_namespace
         ON function_namespace.oid = trigger_function.pronamespace
       JOIN pg_catalog.pg_language function_language
         ON function_language.oid = trigger_function.prolang
      WHERE target_namespace.nspname = 'public'
        AND target.relname = 'auth_tokens'
        AND trigger_state.tgname = $1`,
    [AUTH_TOKEN_TRANSITION_TRIGGER],
  );
  if (result.rowCount === 0) return "absent";
  if (result.rowCount !== 1) return "mismatch";
  const row = result.rows[0]!;
  const exact =
    row.triggerType === 23 &&
    row.triggerEnabled === "O" &&
    !row.internal &&
    row.constraintOid === "0" &&
    !row.deferrable &&
    !row.initiallyDeferred &&
    row.parentOid === "0" &&
    !row.hasQualifier &&
    row.argumentCount === 0 &&
    row.functionName === AUTH_TOKEN_TRANSITION_FUNCTION &&
    row.functionNamespace === "public" &&
    row.functionLanguage === "plpgsql" &&
    row.returnsTrigger &&
    row.functionOwnerMatchesTable &&
    row.securityDefiner &&
    row.volatility === "v" &&
    row.argumentCountFunction === 0 &&
    row.publicCanExecute === false &&
    row.triggerColumns.join(",") === "userId,purpose,usedAt" &&
    row.functionConfig?.length === 1 &&
    row.functionConfig[0] === "search_path=pg_catalog, public, pg_temp" &&
    canonicalSql(row.functionSource) ===
      canonicalSql(AUTH_TOKEN_EXPECTED_TRANSITION_FUNCTION_SOURCE);
  return exact ? "exact" : "mismatch";
}

async function countDuplicateGroups(client: PoolClient): Promise<number> {
  const result = await client.query<{ count: string }>(
    `SELECT COUNT(*)::text AS "count"
       FROM (
         SELECT 1
         FROM public."auth_tokens"
         WHERE "usedAt" IS NULL
         GROUP BY "userId", "purpose"
         HAVING COUNT(*) > 1
       ) duplicate_groups`,
  );
  return safeCount(
    result.rows[0]?.count,
    "AUTH_TOKEN_DUPLICATE_GROUP_COUNT_INVALID",
  );
}

export function assertAuthTokenBatchSize(batchSize: number): number {
  if (!Number.isSafeInteger(batchSize) || batchSize < 1 || batchSize > 1_000) {
    throw new Error("AUTH_TOKEN_LINEARIZATION_BATCH_SIZE_INVALID");
  }
  return batchSize;
}

export async function readAuthTokenLinearizationStatus(
  client: PoolClient,
): Promise<AuthTokenLinearizationStatus> {
  // node-postgres serializes a client's protocol stream. Keep these catalog
  // reads explicitly sequential so status checks do not overlap query() calls
  // on one checked-out connection (deprecated in pg 8 and rejected in pg 9).
  const duplicateGroups = await countDuplicateGroups(client);
  const index = await readIndex(client);
  const transitionTriggerState = await readTransitionTriggerState(client);
  const triggerEnabled = transitionTriggerState === "exact";
  const complete =
    duplicateGroups === 0 &&
    index.exists &&
    index.valid &&
    index.ready &&
    index.live &&
    index.exact &&
    transitionTriggerState === "absent";
  return {
    duplicateGroups,
    indexExists: index.exists,
    indexValid: index.valid && index.live,
    indexReady: index.ready,
    indexExact: index.exact,
    transitionTriggerEnabled: triggerEnabled,
    transitionTriggerState,
    complete,
  };
}

/** Retire older unused rows for at most batchSize authority keys. */
export async function reconcileAuthTokenDuplicateBatch(
  client: PoolClient,
  batchSize: number,
): Promise<{ duplicateKeys: number; retiredRows: number; complete: boolean }> {
  const boundedBatchSize = assertAuthTokenBatchSize(batchSize);
  const index = await readIndex(client);
  const transitionTriggerState = await readTransitionTriggerState(client);
  if (transitionTriggerState === "mismatch") {
    throw new Error("AUTH_TOKEN_TRANSITION_GUARD_MISMATCH");
  }
  if (
    !(index.exists && index.valid && index.ready && index.live && index.exact)
  ) {
    if (transitionTriggerState !== "exact") {
      throw new Error("AUTH_TOKEN_TRANSITION_GUARD_REQUIRED");
    }
  }

  await client.query("BEGIN");
  try {
    await client.query("SET LOCAL lock_timeout = '2s'");
    await client.query("SET LOCAL statement_timeout = '30s'");
    const result = await client.query<{
      duplicateKeys: string;
      retiredRows: string;
    }>(
      `WITH duplicate_keys AS MATERIALIZED (
         SELECT "userId", "purpose"
         FROM public."auth_tokens"
         WHERE "usedAt" IS NULL
         GROUP BY "userId", "purpose"
         HAVING COUNT(*) > 1
         ORDER BY "userId", "purpose"
         LIMIT $1
       ), locked_tokens AS MATERIALIZED (
         SELECT token."id", token."userId", token."purpose",
                token."createdAt"
         FROM public."auth_tokens" token
         JOIN duplicate_keys duplicate_key
           ON duplicate_key."userId" = token."userId"
          AND duplicate_key."purpose" = token."purpose"
         WHERE token."usedAt" IS NULL
         ORDER BY token."userId", token."purpose",
                  token."createdAt" DESC, token."id" DESC
         FOR UPDATE OF token
       ), ranked AS (
         SELECT "id",
           row_number() OVER (
             PARTITION BY "userId", "purpose"
             ORDER BY "createdAt" DESC, "id" DESC
           ) AS ordinal
         FROM locked_tokens
       ), retired AS (
         UPDATE public."auth_tokens" token
         SET "usedAt" = CURRENT_TIMESTAMP
         FROM ranked
         WHERE token."id" = ranked."id"
           AND ranked.ordinal > 1
           AND token."usedAt" IS NULL
         RETURNING token."id"
       )
       SELECT (SELECT COUNT(*)::text FROM duplicate_keys)
                AS "duplicateKeys",
              (SELECT COUNT(*)::text FROM retired) AS "retiredRows"`,
      [boundedBatchSize],
    );
    await client.query("COMMIT");
    const duplicateKeys = safeCount(
      result.rows[0]?.duplicateKeys,
      "AUTH_TOKEN_RECONCILED_KEY_COUNT_INVALID",
    );
    const retiredRows = safeCount(
      result.rows[0]?.retiredRows,
      "AUTH_TOKEN_RETIRED_ROW_COUNT_INVALID",
    );
    return { duplicateKeys, retiredRows, complete: duplicateKeys === 0 };
  } catch (error) {
    await client.query("ROLLBACK").catch(() => undefined);
    throw error;
  }
}

/**
 * Build the final invariant outside a transaction, recover an interrupted
 * invalid shell, catalog-verify it, then remove the transition trigger under
 * a separately bounded metadata transaction.
 */
export async function buildAuthTokenUniqueIndex(
  client: PoolClient,
): Promise<void> {
  if ((await countDuplicateGroups(client)) !== 0) {
    throw new Error("AUTH_TOKEN_DUPLICATES_REMAIN");
  }
  const transitionTriggerState = await readTransitionTriggerState(client);
  if (transitionTriggerState === "mismatch") {
    throw new Error("AUTH_TOKEN_TRANSITION_GUARD_MISMATCH");
  }
  let index = await readIndex(client);
  if (
    !(
      index.exists &&
      index.valid &&
      index.ready &&
      index.live &&
      index.exact
    ) &&
    transitionTriggerState !== "exact"
  ) {
    throw new Error("AUTH_TOKEN_TRANSITION_GUARD_REQUIRED");
  }
  if (
    index.exists &&
    (!index.valid || !index.ready || !index.live) &&
    !index.exact
  ) {
    throw new Error("AUTH_TOKEN_INVALID_INDEX_DEFINITION_MISMATCH");
  }
  if (index.exists && (!index.valid || !index.ready || !index.live)) {
    await client.query(
      `DROP INDEX CONCURRENTLY IF EXISTS public."${AUTH_TOKEN_INDEX}"`,
    );
    index = await readIndex(client);
  }
  if (index.exists && !index.exact) {
    throw new Error("AUTH_TOKEN_INDEX_DEFINITION_MISMATCH");
  }
  if (!index.exists) {
    await client.query(
      `CREATE UNIQUE INDEX CONCURRENTLY "${AUTH_TOKEN_INDEX}"
         ON public."auth_tokens" ("userId", "purpose")
         WHERE "usedAt" IS NULL`,
    );
    index = await readIndex(client);
  }
  if (!(index.valid && index.ready && index.live && index.exact)) {
    throw new Error("AUTH_TOKEN_INDEX_NOT_VALID");
  }

  const finalTriggerState = await readTransitionTriggerState(client);
  if (finalTriggerState === "mismatch") {
    throw new Error("AUTH_TOKEN_TRANSITION_GUARD_MISMATCH");
  }
  if (finalTriggerState === "exact") {
    await client.query("BEGIN");
    try {
      await client.query("SET LOCAL lock_timeout = '2s'");
      await client.query("SET LOCAL statement_timeout = '30s'");
      await client.query(
        `DROP TRIGGER IF EXISTS "${AUTH_TOKEN_TRANSITION_TRIGGER}"
           ON public."auth_tokens"`,
      );
      await client.query("COMMIT");
    } catch (error) {
      await client.query("ROLLBACK").catch(() => undefined);
      throw error;
    }
  }

  const status = await readAuthTokenLinearizationStatus(client);
  if (!status.complete) throw new Error("AUTH_TOKEN_LINEARIZATION_INCOMPLETE");
}
