#!/usr/bin/env tsx

// Actual-PostgreSQL proof for the shared client's startup options. The script
// is read-only and accepts only an explicitly named disposable test target.

import assert from "node:assert/strict";

import { Client } from "pg";

import { assertNonProdDatabase } from "../src/db-guard";
import {
  buildDatabaseConnectionString,
  DATABASE_SEARCH_PATH,
} from "../src/database-connection-string";

const raw = process.env.DATABASE_CONNECTION_OPTIONS_TEST_DATABASE_URL?.trim();
if (!raw) {
  throw new Error("DATABASE_CONNECTION_OPTIONS_TEST_DATABASE_URL_REQUIRED");
}
assertNonProdDatabase(raw);

const timeoutMs = 250;
const sourceUrl = new URL(raw);
if (sourceUrl.searchParams.has("options")) {
  throw new Error(
    "DATABASE_CONNECTION_OPTIONS_TEST_URL_OPTIONS_MUST_BE_ABSENT",
  );
}
sourceUrl.searchParams.set("options", `-c search_path=${DATABASE_SEARCH_PATH}`);
const sourceConnectionString = sourceUrl.toString();
const expectedOptions = `-c search_path=${DATABASE_SEARCH_PATH} -c statement_timeout=${timeoutMs}`;
const connectionString = buildDatabaseConnectionString(
  sourceConnectionString,
  timeoutMs,
);
const client = new Client({ connectionString });

let prisma: {
  $queryRaw: (query: TemplateStringsArray) => Promise<unknown[]>;
  $disconnect: () => Promise<void>;
} | null = null;

async function main(): Promise<void> {
  try {
    await client.connect();

    const settings = await client.query<{
      searchPath: string;
      statementTimeout: string;
      currentSchema: string;
    }>(`
      SELECT
        current_setting('search_path') AS "searchPath",
        current_setting('statement_timeout') AS "statementTimeout",
        current_schema() AS "currentSchema"
    `);

    assert.equal(settings.rows[0]?.searchPath, DATABASE_SEARCH_PATH);
    assert.equal(settings.rows[0]?.statementTimeout, `${timeoutMs}ms`);
    assert.equal(settings.rows[0]?.currentSchema, "pg_catalog");

    const parsedOptions = (
      client as unknown as { connectionParameters: { options?: string } }
    ).connectionParameters.options;
    assert.equal(parsedOptions, expectedOptions);

    await assert.rejects(
      client.query("SELECT pg_sleep(1)"),
      (error: unknown) =>
        typeof error === "object" &&
        error !== null &&
        "code" in error &&
        error.code === "57014",
      "statement_timeout must cancel an over-budget statement",
    );

    // Exercise the shared production client entry point as well as the pure
    // builder, so the proof fails if index.ts stops using this contract.
    process.env.DATABASE_URL = sourceConnectionString;
    process.env.PRISMA_STATEMENT_TIMEOUT_MS = String(timeoutMs);
    const dbModule = await import("../src/index");
    const connectedPrisma = dbModule.default as NonNullable<typeof prisma>;
    prisma = connectedPrisma;
    const prismaSettings = (await connectedPrisma.$queryRaw`
      SELECT
        current_setting('search_path') AS "searchPath",
        current_setting('statement_timeout') AS "statementTimeout",
        current_schema() AS "currentSchema"
    `) as Array<{
      searchPath: string;
      statementTimeout: string;
      currentSchema: string;
    }>;
    assert.equal(prismaSettings[0]?.searchPath, DATABASE_SEARCH_PATH);
    assert.equal(prismaSettings[0]?.statementTimeout, `${timeoutMs}ms`);
    assert.equal(prismaSettings[0]?.currentSchema, "pg_catalog");

    process.stdout.write("DATABASE_CONNECTION_OPTIONS_PG_TEST_PASS\n");
  } finally {
    await prisma?.$disconnect().catch(() => undefined);
    await client.end().catch(() => undefined);
  }
}

void main();
