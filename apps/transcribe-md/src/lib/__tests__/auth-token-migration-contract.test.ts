import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { AUTH_TOKEN_EXPECTED_TRANSITION_FUNCTION_SOURCE } from "../../../../../packages/db/src/auth-token-linearization-online";

const migration = readFileSync(
  resolve(
    process.cwd(),
    "../../packages/db/prisma/migrations/20260720150000_auth_token_linearization_v5/migration.sql",
  ),
  "utf8",
);
const operator = readFileSync(
  resolve(
    process.cwd(),
    "../../packages/db/src/auth-token-linearization-online.ts",
  ),
  "utf8",
);
const cli = readFileSync(
  resolve(
    process.cwd(),
    "../../packages/db/scripts/auth-token-linearization-online.ts",
  ),
  "utf8",
);

describe("auth-token linearization migration contract", () => {
  it("keeps prisma migrate deploy expand-only and transition guarded", () => {
    expect(migration).toContain("auth_tokens_guard_one_unused_transition");
    expect(migration).toContain("pg_advisory_xact_lock(hashtextextended(");
    expect(migration).toContain("ERRCODE = '23505'");
    expect(migration).toContain(
      "current_setting('transaction_isolation') <> 'read committed'",
    );
    expect(migration).toContain("ERRCODE = '25000'");
    expect(migration).toContain("aaa_auth_tokens_one_unused_transition");
    expect(migration).toContain("SET LOCAL lock_timeout = '2s'");
    expect(migration).toContain("SET LOCAL statement_timeout = '30s'");
    expect(migration).not.toMatch(/^\s*CREATE UNIQUE INDEX/mu);
    expect(migration).not.toMatch(/UPDATE public\."auth_tokens"/u);
  });

  it("retires every historical duplicate except the newest in bounded batches", () => {
    expect(operator).toMatch(/PARTITION BY "userId", "purpose"/u);
    expect(operator).toMatch(/ORDER BY "createdAt" DESC, "id" DESC/u);
    expect(operator).toContain("ranked.ordinal > 1");
    expect(operator).toContain('SET "usedAt" = CURRENT_TIMESTAMP');
    expect(operator).toContain("LIMIT $1");
    expect(operator).toContain("FOR UPDATE OF token");
    expect(operator).toContain("batchSize > 1_000");
  });

  it("builds and verifies the final invariant online", () => {
    expect(operator).toContain("CREATE UNIQUE INDEX CONCURRENTLY");
    expect(operator).toContain("DROP INDEX CONCURRENTLY IF EXISTS");
    expect(operator).toContain("indisvalid");
    expect(operator).toContain("indisready");
    expect(operator).toContain("indislive");
    expect(operator).toContain("indnkeyatts");
    expect(operator).toContain("indnatts");
    expect(operator).toContain("indnullsnotdistinct");
    expect(operator).toContain("EXPECTED_INDEX_DEFINITION");
    expect(operator).toContain('row.accessMethod === "btree"');
    expect(operator).toContain("!row.hasExpressions");
    expect(operator).toContain(
      "AUTH_TOKEN_EXPECTED_TRANSITION_FUNCTION_SOURCE",
    );
    expect(operator).toContain("row.triggerType === 23");
    expect(operator).toContain('row.parentOid === "0"');
    expect(operator).toContain("!row.hasQualifier");
    expect(operator).toContain('row.functionLanguage === "plpgsql"');
    expect(operator).toContain("row.returnsTrigger");
    expect(operator).toContain("row.functionOwnerMatchesTable");
    expect(operator).toContain('return exact ? "exact" : "mismatch"');
    expect(operator).toContain("AUTH_TOKEN_TRANSITION_GUARD_MISMATCH");
    expect(operator).toContain(
      'row.triggerColumns.join(",") === "userId,purpose,usedAt"',
    );
    expect(operator).toContain("AUTH_TOKEN_INDEX_DEFINITION_MISMATCH");
    expect(operator.indexOf("AUTH_TOKEN_INDEX_NOT_VALID")).toBeLessThan(
      operator.indexOf('LOCK TABLE public."auth_tokens"'),
    );
    expect(operator).toContain(
      'LOCK TABLE public."auth_tokens" IN ACCESS EXCLUSIVE MODE',
    );
    expect(operator).toContain(
      'DROP TRIGGER "${AUTH_TOKEN_TRANSITION_TRIGGER}"',
    );
    expect(operator).not.toContain(
      'DROP TRIGGER IF EXISTS "${AUTH_TOKEN_TRANSITION_TRIGGER}"',
    );
  });

  it("requires one session lock and explicit production change control", () => {
    expect(cli).toContain(
      "acquireAuthTokenOperatorSessionLockOnClient(client)",
    );
    expect(cli).toContain("max: 1");
    expect(cli).toContain("AUTH_TOKEN_LINEARIZATION_ALLOW_PRODUCTION");
    expect(cli).toContain("AUTH_TOKEN_LINEARIZATION_PRODUCTION_CHANGE_ID");
    expect(cli).toContain("AUTH_TOKEN_LINEARIZATION_PRODUCTION_ACK");
    expect(cli).toContain("buildDatabaseConnectionString");
    expect(cli).toContain("AUTH_TOKEN_OPERATOR_LOCK_TIMEOUT_MS = 2_000");
    expect(cli).toContain(
      "AUTH_TOKEN_OPERATOR_INDEX_STATEMENT_TIMEOUT_MS = 15 * 60_000",
    );
    expect(cli).toContain(
      "AUTH_TOKEN_LINEARIZATION_APPROVED_TARGET_FINGERPRINT",
    );
    expect(cli).toContain("preflightAuthTokenOperatorTarget");
    expect(cli).toContain(
      'phase === "status" ? { defaultTransactionReadOnly: true }',
    );
    expect(cli).toContain('["tlsIdentity", target.tlsIdentity]');
    expect(cli).toContain('["phase", phase]');
    expect(cli).toContain('["inRecovery", target.inRecovery]');
    expect(cli).toContain("authTokenOperatorProtocolEpoch");
    expect(cli).toContain('const AUTH_TOKEN_OPERATOR_PRINCIPAL = "meddoc"');
    expect(cli).toContain("pg_catalog.pg_is_in_recovery()");
    expect(cli).toContain("SAFE_INTERNAL_ERROR_CODES");
    expect(cli).not.toContain("/^[A-Z0-9_]+$/");
  });

  it("keeps the migration and operator transition function source identical", () => {
    const marker =
      "CREATE OR REPLACE FUNCTION public.auth_tokens_guard_one_unused_transition()";
    const start = migration.indexOf(marker);
    expect(start).toBeGreaterThanOrEqual(0);
    const body = migration.slice(start).match(/AS \$\$([\s\S]*?)\$\$;/u)?.[1];
    expect(body?.replace(/\s+/gu, " ").trim()).toBe(
      AUTH_TOKEN_EXPECTED_TRANSITION_FUNCTION_SOURCE.replace(
        /\s+/gu,
        " ",
      ).trim(),
    );
  });
});
