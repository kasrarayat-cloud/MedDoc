import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import type { PoolClient } from "pg";
import { describe, expect, it, vi } from "vitest";

import {
  assertApprovedAuthTokenOperatorTarget,
  authTokenOperatorTargetFingerprint,
  buildAuthTokenOperatorConnectionString,
  parseAuthTokenOperatorArgs,
  preflightAuthTokenOperatorTarget,
  safeAuthTokenOperatorErrorCode,
  type AuthTokenOperatorTarget,
} from "./auth-token-linearization-online";

const repositoryRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../..",
);
const tsx = resolve(repositoryRoot, "node_modules/.bin/tsx");
const entrypoint = resolve(
  repositoryRoot,
  "packages/db/scripts/auth-token-linearization-online.ts",
);

const TARGET: AuthTokenOperatorTarget = {
  host: "postgres.internal",
  port: 5432,
  database: "meddoc_auth_test",
  login: "meddoc_release_security",
  serverAddress: "192.0.2.10",
  serverPort: 5432,
  postgresMajor: 16,
  tlsIdentity: `x509-authorized-sha256:${"a".repeat(64)}`,
};

const SESSION_ROW = {
  sessionRole: "meddoc_release_security",
  currentRole: "meddoc_release_security",
  database: "meddoc_auth_test",
  serverAddress: "192.0.2.10",
  serverPort: 5432,
  serverVersionNumber: 160_010,
  searchPath: "pg_catalog,public",
  statementTimeoutMs: 30_000,
  lockTimeoutMs: 2_000,
  applicationName: "quillmd_auth_token_linearization_online_v1",
  transactionReadOnly: "off",
  ssl: false,
};

function sessionClient(
  overrides: Record<string, unknown> = {},
  rowOverrides: Record<string, unknown> = {},
): PoolClient {
  return {
    host: "postgres.internal",
    port: 5432,
    database: "meddoc_auth_test",
    user: "meddoc_release_security",
    connection: { stream: { encrypted: false } },
    query: vi.fn().mockResolvedValue({
      rows: [{ ...SESSION_ROW, ...rowOverrides }],
    }),
    ...overrides,
  } as unknown as PoolClient;
}

async function runOperator(
  args: string[],
  databaseUrl: string,
): Promise<{ code: number | null; stdout: string; stderr: string }> {
  return new Promise((resolveResult, reject) => {
    const child = spawn(tsx, [entrypoint, ...args], {
      cwd: repositoryRoot,
      env: {
        PATH: process.env.PATH,
        VITEST: "false",
        AUTH_TOKEN_LINEARIZATION_DATABASE_URL: databaseUrl,
      },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8").on("data", (chunk: string) => {
      stdout += chunk;
    });
    child.stderr.setEncoding("utf8").on("data", (chunk: string) => {
      stderr += chunk;
    });
    child.once("error", reject);
    child.once("close", (code) => resolveResult({ code, stdout, stderr }));
  });
}

describe("auth-token online operator fixed-output entrypoint", () => {
  it("requires each CLI control at most once", () => {
    expect(() =>
      parseAuthTokenOperatorArgs(["--phase", "status", "--phase", "reconcile"]),
    ).toThrow("Duplicate argument: --phase");
  });

  it("uses the shared canonical options contract and makes status read-only", () => {
    const base =
      "postgresql://meddoc_release_security:synthetic@postgres.internal:5432/meddoc_auth_test?schema=public";
    const status = new URL(
      buildAuthTokenOperatorConnectionString(base, "status"),
    );
    const index = new URL(
      buildAuthTokenOperatorConnectionString(base, "index"),
    );

    expect(status.searchParams.getAll("options")).toEqual([
      "-c search_path=pg_catalog,public -c statement_timeout=30000 -c lock_timeout=2000 -c application_name=quillmd_auth_token_linearization_online_v1 -c default_transaction_read_only=on",
    ]);
    expect(index.searchParams.getAll("options")).toEqual([
      "-c search_path=pg_catalog,public -c statement_timeout=900000 -c lock_timeout=2000 -c application_name=quillmd_auth_token_linearization_online_v1",
    ]);
  });

  it.each([
    ["duplicate options", "&options=x&options=y"],
    ["unreviewed GUC", "&options=-c%20role%3Downer"],
    ["direct GUC", "&application_name=alternate"],
    ["query target override", "&host=alternate"],
    ["surrounding whitespace", " "],
  ])("rejects a noncanonical operator URL: %s", (_label, suffix) => {
    const base =
      "postgresql://meddoc_release_security:synthetic@postgres.internal:5432/meddoc_auth_test?schema=public";
    const raw = suffix === " " ? `${base}${suffix}` : `${base}${suffix}`;
    expect(() =>
      buildAuthTokenOperatorConnectionString(raw, "reconcile"),
    ).toThrow("DATABASE_CONNECTION_OPTIONS_INVALID");
  });

  it("binds approval to every reviewed target dimension and phase", () => {
    const approved = authTokenOperatorTargetFingerprint(TARGET, "reconcile");
    expect(() =>
      assertApprovedAuthTokenOperatorTarget(TARGET, "reconcile", approved),
    ).not.toThrow();

    const alternatives: AuthTokenOperatorTarget[] = [
      { ...TARGET, host: "alternate.internal" },
      { ...TARGET, port: 5433 },
      { ...TARGET, database: "alternate_auth_test" },
      { ...TARGET, login: "alternate_login" },
      { ...TARGET, tlsIdentity: `x509-authorized-sha256:${"b".repeat(64)}` },
      { ...TARGET, serverAddress: "192.0.2.11" },
      { ...TARGET, serverPort: 5433 },
      { ...TARGET, postgresMajor: 17 },
    ];
    for (const target of alternatives) {
      expect(authTokenOperatorTargetFingerprint(target, "reconcile")).not.toBe(
        approved,
      );
      expect(() =>
        assertApprovedAuthTokenOperatorTarget(target, "reconcile", approved),
      ).toThrow("AUTH_TOKEN_LINEARIZATION_TARGET_APPROVAL_MISMATCH");
    }
    expect(authTokenOperatorTargetFingerprint(TARGET, "index")).not.toBe(
      approved,
    );
    expect(() =>
      assertApprovedAuthTokenOperatorTarget(TARGET, "index", approved),
    ).toThrow("AUTH_TOKEN_LINEARIZATION_TARGET_APPROVAL_MISMATCH");
    for (const absentOrNoncanonical of [
      undefined,
      "",
      approved.toUpperCase(),
      `${approved} `,
    ]) {
      expect(() =>
        assertApprovedAuthTokenOperatorTarget(
          TARGET,
          "reconcile",
          absentOrNoncanonical,
        ),
      ).toThrow("AUTH_TOKEN_LINEARIZATION_TARGET_APPROVAL_REQUIRED");
    }
  });

  it.each([
    ["client host", { host: "alternate.internal" }, {}],
    ["client port", { port: 5433 }, {}],
    ["client login", { user: "alternate_login" }, {}],
    ["session login", {}, { sessionRole: "alternate_login" }],
    ["current role", {}, { currentRole: "alternate_login" }],
    ["database", {}, { database: "alternate_auth_test" }],
    ["server address", {}, { serverAddress: null }],
    ["invalid server port", {}, { serverPort: 0 }],
    ["server major", {}, { serverVersionNumber: 170_000 }],
    ["search path", {}, { searchPath: "public" }],
    ["phase timeout", {}, { statementTimeoutMs: 900_000 }],
    ["TLS transport", {}, { ssl: true }],
  ])(
    "rejects live %s drift before mutation",
    async (_label, clientOverrides, rowOverrides) => {
      await expect(
        preflightAuthTokenOperatorTarget(
          sessionClient(clientOverrides, rowOverrides),
          {
            host: "postgres.internal",
            port: 5432,
            database: "meddoc_auth_test",
            login: "meddoc_release_security",
          },
          "reconcile",
        ),
      ).rejects.toThrow("AUTH_TOKEN_LINEARIZATION_SESSION_TARGET_MISMATCH");
    },
  );

  it("accepts only the exact live non-TLS session and enforces status read-only", async () => {
    await expect(
      preflightAuthTokenOperatorTarget(
        sessionClient(),
        {
          host: "postgres.internal",
          port: 5432,
          database: "meddoc_auth_test",
          login: "meddoc_release_security",
        },
        "reconcile",
      ),
    ).resolves.toEqual({
      host: "postgres.internal",
      port: 5432,
      database: "meddoc_auth_test",
      login: "meddoc_release_security",
      serverAddress: "192.0.2.10",
      serverPort: 5432,
      postgresMajor: 16,
      tlsIdentity: "plaintext",
    });

    await expect(
      preflightAuthTokenOperatorTarget(
        sessionClient({}, { transactionReadOnly: "on" }),
        {
          host: "postgres.internal",
          port: 5432,
          database: "meddoc_auth_test",
          login: "meddoc_release_security",
        },
        "status",
      ),
    ).resolves.toMatchObject({ tlsIdentity: "plaintext" });
  });

  it("never treats an arbitrary uppercase exception as a printable code", () => {
    expect(
      safeAuthTokenOperatorErrorCode(
        new Error("SYNTHETIC_UPPERCASE_SECRET_SENTINEL"),
      ),
    ).toBe("AUTH_TOKEN_LINEARIZATION_OPERATOR_FAILED");
    expect(
      safeAuthTokenOperatorErrorCode(
        new Error("AUTH_TOKEN_TRANSITION_GUARD_MISMATCH"),
      ),
    ).toBe("AUTH_TOKEN_TRANSITION_GUARD_MISMATCH");
  });

  it.each([
    {
      label: "malformed connection URL",
      args: ["--phase", "status"],
      url: "postgresql://synthetic:synthetic-url-secret@[",
      sentinel: "synthetic-url-secret",
    },
    {
      label: "connection failure",
      args: ["--phase", "status"],
      url: "postgresql://synthetic:synthetic-connect-secret@127.0.0.1:1/meddoc_operator_test",
      sentinel: "synthetic-connect-secret",
    },
    {
      label: "argument failure",
      args: ["--phase", "status", "--synthetic-argument-secret"],
      url: "postgresql://synthetic:synthetic-argument-url-secret@127.0.0.1:1/meddoc_operator_test",
      sentinel: "synthetic-argument-secret",
    },
  ])("redacts $label", async ({ args, url, sentinel }) => {
    const result = await runOperator(args, url);
    expect(result.code).not.toBe(0);
    expect(result.stdout).toBe("");
    expect(result.stderr).toBe("AUTH_TOKEN_LINEARIZATION_OPERATOR_FAILED\n");
    expect(`${result.stdout}${result.stderr}`).not.toContain(sentinel);
    expect(`${result.stdout}${result.stderr}`).not.toContain("password");
  });
});
