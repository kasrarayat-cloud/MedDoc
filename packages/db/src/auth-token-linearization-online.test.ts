import type { PoolClient } from "pg";
import { describe, expect, it, vi } from "vitest";

import {
  AUTH_TOKEN_EXPECTED_TRANSITION_FUNCTION_SOURCE,
  buildAuthTokenUniqueIndex,
  readAuthTokenLinearizationStatusSnapshot,
} from "./auth-token-linearization-online";

const EXACT_INDEX_ROW = {
  exists: true,
  isValid: true,
  isReady: true,
  isLive: true,
  isUnique: true,
  keyAttributeCount: 2,
  attributeCount: 2,
  accessMethod: "btree",
  hasExpressions: false,
  nullsNotDistinct: false,
  definition:
    'CREATE UNIQUE INDEX auth_tokens_one_unused_per_user_purpose ON public.auth_tokens USING btree ("userId", purpose) WHERE ("usedAt" IS NULL)',
  tableName: "auth_tokens",
  columnOne: '"userId"',
  columnTwo: "purpose",
  predicate: '("usedAt" IS NULL)',
};

const EXACT_TRIGGER_ROW = {
  triggerType: 23,
  triggerColumns: ["userId", "purpose", "usedAt"],
  triggerEnabled: "O",
  internal: false,
  constraintOid: "0",
  deferrable: false,
  initiallyDeferred: false,
  parentOid: "0",
  hasQualifier: false,
  argumentCount: 0,
  functionName: "auth_tokens_guard_one_unused_transition",
  functionNamespace: "public",
  functionLanguage: "plpgsql",
  returnsTrigger: true,
  functionOwnerMatchesTable: true,
  securityDefiner: true,
  volatility: "v",
  argumentCountFunction: 0,
  functionConfig: ["search_path=pg_catalog, public, pg_temp"],
  functionSource: AUTH_TOKEN_EXPECTED_TRANSITION_FUNCTION_SOURCE,
  publicCanExecute: false,
};

function result(rows: unknown[]) {
  return { rows, rowCount: rows.length, command: "", oid: 0, fields: [] };
}

function finalizationClient(options: { driftUnderLock?: boolean } = {}) {
  let triggerPresent = true;
  let indexReads = 0;
  const query = vi.fn(async (sql: string) => {
    if (sql.includes("FROM pg_catalog.pg_class index_object")) {
      indexReads += 1;
      return result([
        options.driftUnderLock && indexReads === 2
          ? { ...EXACT_INDEX_ROW, definition: "CREATE INDEX mismatched" }
          : EXACT_INDEX_ROW,
      ]);
    }
    if (sql.includes("FROM pg_catalog.pg_trigger trigger_state")) {
      return result(triggerPresent ? [EXACT_TRIGGER_ROW] : []);
    }
    if (sql.includes("HAVING COUNT(*) > 1")) {
      return result([{ count: "0" }]);
    }
    if (sql.includes("DROP TRIGGER")) {
      triggerPresent = false;
    }
    return result([]);
  });
  return {
    client: { query } as unknown as PoolClient,
    query,
  };
}

describe("auth-token final invariant linearization", () => {
  it("locks the table, re-proves exact preconditions, drops exactly, and proves final state before commit", async () => {
    const { client, query } = finalizationClient();

    await expect(buildAuthTokenUniqueIndex(client)).resolves.toBeUndefined();

    const calls = query.mock.calls.map(([sql]) => String(sql));
    const lockAt = calls.findIndex((sql) =>
      sql.includes('LOCK TABLE public."auth_tokens" IN ACCESS EXCLUSIVE MODE'),
    );
    const dropAt = calls.findIndex((sql) => sql.includes("DROP TRIGGER"));
    const commitAt = calls.findIndex((sql) => sql === "COMMIT");
    const indexReads = calls
      .map((sql, index) =>
        sql.includes("FROM pg_catalog.pg_class index_object") ? index : -1,
      )
      .filter((index) => index >= 0);
    const triggerReads = calls
      .map((sql, index) =>
        sql.includes("FROM pg_catalog.pg_trigger trigger_state") ? index : -1,
      )
      .filter((index) => index >= 0);
    const duplicateProofs = calls
      .map((sql, index) => (sql.includes("HAVING COUNT(*) > 1") ? index : -1))
      .filter((index) => index >= 0);

    expect(lockAt).toBeGreaterThan(-1);
    expect(dropAt).toBeGreaterThan(lockAt);
    expect(calls[dropAt]).not.toContain("IF EXISTS");
    expect(indexReads.some((index) => lockAt < index && index < dropAt)).toBe(
      true,
    );
    expect(triggerReads.some((index) => lockAt < index && index < dropAt)).toBe(
      true,
    );
    expect(
      duplicateProofs.some((index) => lockAt < index && index < dropAt),
    ).toBe(true);
    expect(indexReads.some((index) => dropAt < index && index < commitAt)).toBe(
      true,
    );
    expect(
      triggerReads.some((index) => dropAt < index && index < commitAt),
    ).toBe(true);
    expect(
      duplicateProofs.some((index) => dropAt < index && index < commitAt),
    ).toBe(true);
  });

  it("rolls back without dropping when the exact index drifts under the table lock", async () => {
    const { client, query } = finalizationClient({ driftUnderLock: true });

    await expect(buildAuthTokenUniqueIndex(client)).rejects.toThrow(
      "AUTH_TOKEN_INDEX_NOT_VALID",
    );

    const calls = query.mock.calls.map(([sql]) => String(sql));
    expect(calls).toContain(
      'LOCK TABLE public."auth_tokens" IN ACCESS EXCLUSIVE MODE',
    );
    expect(calls.some((sql) => sql.includes("DROP TRIGGER"))).toBe(false);
    expect(calls).toContain("ROLLBACK");
  });

  it("reads an approval status in one repeatable-read, read-only snapshot", async () => {
    const { client, query } = finalizationClient();

    await expect(
      readAuthTokenLinearizationStatusSnapshot(client),
    ).resolves.toMatchObject({
      duplicateGroups: 0,
      indexExact: true,
      transitionTriggerState: "exact",
      complete: false,
    });

    expect(query.mock.calls[0]?.[0]).toBe(
      "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY",
    );
    expect(query.mock.calls.at(-1)?.[0]).toBe("COMMIT");
  });
});
