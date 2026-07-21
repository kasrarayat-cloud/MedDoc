import { parse as parsePgConnectionString } from "pg-connection-string";
import { describe, expect, it } from "vitest";

import {
  buildDatabaseConnectionString,
  buildRuntimeDatabaseConnectionString,
  DATABASE_SEARCH_PATH,
  parseStatementTimeoutMs,
} from "./database-connection-string";

const BASE =
  "postgresql://runtime:synthetic@postgres:5432/meddoc?schema=public";
const SEARCH_PATH_ONLY = "-c search_path=pg_catalog,public";
const EFFECTIVE_OPTIONS =
  "-c search_path=pg_catalog,public -c statement_timeout=30000";

function optionsFromActualDriverParser(connectionString: string): string {
  return String(parsePgConnectionString(connectionString).options);
}

describe("database connection startup options", () => {
  it.each([undefined, "250", "900000"])(
    "builds the environment-selected runtime timeout identically (%s)",
    (timeout) => {
      const environment = { PRISMA_STATEMENT_TIMEOUT_MS: timeout };
      expect(buildRuntimeDatabaseConnectionString(BASE, environment)).toBe(
        buildDatabaseConnectionString(BASE, timeout),
      );
    },
  );

  it.each(["", " ", "0", "1.5", "2147483648"])(
    "rejects an unsafe runtime environment timeout (%s)",
    (timeout) => {
      expect(() =>
        buildRuntimeDatabaseConnectionString(BASE, {
          PRISMA_STATEMENT_TIMEOUT_MS: timeout,
        }),
      ).toThrow("DATABASE_CONNECTION_OPTIONS_INVALID:STATEMENT_TIMEOUT");
    },
  );

  it("builds one effective options value containing both required settings", () => {
    const result = buildDatabaseConnectionString(BASE, 30_000);

    expect(new URL(result).searchParams.getAll("options")).toEqual([
      EFFECTIVE_OPTIONS,
    ]);
    expect(optionsFromActualDriverParser(result)).toBe(EFFECTIVE_OPTIONS);
    expect(optionsFromActualDriverParser(result)).toContain(
      `search_path=${DATABASE_SEARCH_PATH}`,
    );
    expect(optionsFromActualDriverParser(result)).toContain(
      "statement_timeout=30000",
    );
  });

  it("preserves the reviewed search path while adding the timeout", () => {
    const raw = `${BASE}&options=${encodeURIComponent(SEARCH_PATH_ONLY)}`;
    const result = buildDatabaseConnectionString(raw, 30_000);

    expect(optionsFromActualDriverParser(result)).toBe(EFFECTIVE_OPTIONS);
    expect(new URL(result).searchParams.getAll("options")).toHaveLength(1);
  });

  it("is idempotent for the exact completed options contract", () => {
    const once = buildDatabaseConnectionString(BASE, 30_000);
    const twice = buildDatabaseConnectionString(once, 30_000);

    expect(optionsFromActualDriverParser(twice)).toBe(EFFECTIVE_OPTIONS);
    expect(new URL(twice).searchParams.getAll("options")).toHaveLength(1);
  });

  it("builds a finite operator startup contract in the same canonical channel", () => {
    const result = buildDatabaseConnectionString(BASE, 900_000, {
      lockTimeoutMs: 2_000,
      applicationName: "quillmd_auth_token_linearization_online_v1",
      defaultTransactionReadOnly: true,
    });

    expect(new URL(result).searchParams.getAll("options")).toEqual([
      "-c search_path=pg_catalog,public -c statement_timeout=900000 -c lock_timeout=2000 -c application_name=quillmd_auth_token_linearization_online_v1 -c default_transaction_read_only=on",
    ]);
    expect(
      buildDatabaseConnectionString(result, 900_000, {
        lockTimeoutMs: 2_000,
        applicationName: "quillmd_auth_token_linearization_online_v1",
        defaultTransactionReadOnly: true,
      }),
    ).toBe(result);
  });

  it.each([
    [
      "duplicate options",
      `${BASE}&options=${encodeURIComponent(SEARCH_PATH_ONLY)}&options=${encodeURIComponent(EFFECTIVE_OPTIONS)}`,
      "DUPLICATE_OPTIONS",
    ],
    [
      "encoded duplicate options key",
      `${BASE}&options=${encodeURIComponent(SEARCH_PATH_ONLY)}&opt%69ons=${encodeURIComponent(EFFECTIVE_OPTIONS)}`,
      "DUPLICATE_OPTIONS",
    ],
    [
      "case-ambiguous options key",
      `${BASE}&Options=${encodeURIComponent(SEARCH_PATH_ONLY)}`,
      "AMBIGUOUS_OPTIONS_KEY",
    ],
    [
      "noncanonical search path",
      `${BASE}&options=${encodeURIComponent("-c search_path=public")}`,
      "UNREVIEWED_OPTIONS",
    ],
    [
      "extra startup setting",
      `${BASE}&options=${encodeURIComponent(`${SEARCH_PATH_ONLY} -c role=owner`)}`,
      "UNREVIEWED_OPTIONS",
    ],
    [
      "timeout without search path",
      `${BASE}&options=${encodeURIComponent("-c statement_timeout=30000")}`,
      "UNREVIEWED_OPTIONS",
    ],
    [
      "different timeout",
      `${BASE}&options=${encodeURIComponent(`${SEARCH_PATH_ONLY} -c statement_timeout=1`)}`,
      "UNREVIEWED_OPTIONS",
    ],
    [
      "direct timeout parameter",
      `${BASE}&statement_timeout=30000`,
      "SETTING_OUTSIDE_CANONICAL_OPTIONS",
    ],
    [
      "direct search-path parameter",
      `${BASE}&search_path=pg_catalog%2Cpublic`,
      "SETTING_OUTSIDE_CANONICAL_OPTIONS",
    ],
    ["empty options", `${BASE}&options=`, "UNREVIEWED_OPTIONS"],
    [
      "malformed options encoding",
      `${BASE}&options=%ZZ`,
      "MALFORMED_QUERY_ENCODING",
    ],
    ["URL fragment", `${BASE}#options=ignored`, "DATABASE_URL_FRAGMENT"],
    [
      "duplicate ordinary query key",
      `${BASE}&schema=public`,
      "DUPLICATE_QUERY_KEY",
    ],
    ["empty query entry", `${BASE}&&sslmode=disable`, "EMPTY_QUERY_ENTRY"],
    ["empty query key", `${BASE}&=value`, "EMPTY_QUERY_KEY"],
    [
      "query user override",
      `${BASE}&user=alternate`,
      "IDENTITY_OUTSIDE_URL_AUTHORITY",
    ],
    [
      "encoded query host override",
      `${BASE}&ho%73t=alternate`,
      "IDENTITY_OUTSIDE_URL_AUTHORITY",
    ],
    [
      "case-ambiguous query port override",
      `${BASE}&Port=5433`,
      "AMBIGUOUS_IDENTITY_KEY",
    ],
    [
      "direct application name",
      `${BASE}&application_name=alternate`,
      "SETTING_OUTSIDE_CANONICAL_OPTIONS",
    ],
    [
      "direct lock timeout",
      `${BASE}&lock_timeout=1`,
      "SETTING_OUTSIDE_CANONICAL_OPTIONS",
    ],
    ["direct role", `${BASE}&role=meddoc`, "SETTING_OUTSIDE_CANONICAL_OPTIONS"],
    [
      "noncanonical surrounding whitespace",
      ` ${BASE}`,
      "DATABASE_URL_NOT_CANONICAL",
    ],
    [
      "non-Postgres protocol",
      "https://postgres/meddoc",
      "DATABASE_URL_PROTOCOL",
    ],
  ])("rejects %s", (_label, raw, errorCode) => {
    expect(() => buildDatabaseConnectionString(raw, 30_000)).toThrow(
      `DATABASE_CONNECTION_OPTIONS_INVALID:${errorCode}`,
    );
  });

  it.each(["", "0", "-1", "1.5", " 30000", "30s", NaN, Infinity, 0, -1, 1.5])(
    "rejects an unsafe statement timeout (%s)",
    (value) => {
      expect(() => parseStatementTimeoutMs(value)).toThrow(
        "DATABASE_CONNECTION_OPTIONS_INVALID:STATEMENT_TIMEOUT",
      );
    },
  );

  it("rejects a timeout larger than PostgreSQL's integer GUC bound", () => {
    expect(() => parseStatementTimeoutMs(2_147_483_648)).toThrow(
      "DATABASE_CONNECTION_OPTIONS_INVALID:STATEMENT_TIMEOUT_OUT_OF_RANGE",
    );
  });
});
