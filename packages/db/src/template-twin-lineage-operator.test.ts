import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import type { PoolClient } from "pg";
import { describe, expect, it, vi } from "vitest";

import {
  assertApprovedLineageOperatorTarget,
  buildLineageOperatorConnectionString,
  createLineageSessionClient,
  lineageOperatorApprovalFingerprint,
  lineageStatusForOutput,
  lineageOperatorTargetFingerprint,
  parseLineageOperatorArgs,
  preflightLineageOperatorTarget,
  safeLineageOperatorDiagnosticCode,
  safeLineageOperatorErrorCode,
  type LineageOperatorTarget,
} from "../scripts/template-twin-lineage-online";
import type { LineageMigrationStatus } from "./template-twin-lineage-online";

const repositoryRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../..",
);
const tsx = resolve(repositoryRoot, "node_modules/.bin/tsx");
const entrypoint = resolve(
  repositoryRoot,
  "packages/db/scripts/template-twin-lineage-online.ts",
);

const TARGET: LineageOperatorTarget = {
  host: "postgres.internal",
  port: 5432,
  database: "meddoc_lineage_test",
  login: "meddoc",
  serverAddress: "192.0.2.20",
  serverPort: 5432,
  serverVersionNumber: 160_013,
  systemIdentifier: "7623456789012345678",
  tlsIdentity: "plaintext",
  inRecovery: false,
};

const STATUS: LineageMigrationStatus = {
  operationKey: "note_templates_lineage_v1",
  phase: "EXPANDED",
  lastProcessedId: null,
  rowsProcessed: 0,
  batchCount: 0,
  lastBatchRows: 0,
  lastErrorCode: null,
  startedAt: null,
  updatedAt: "2026-07-20T00:00:00.000Z",
  completedAt: null,
  nullRows: 2,
  duplicateLineageVersions: 0,
  partialIndex: { exists: false, valid: false, ready: false },
  finalIndex: { exists: false, valid: false, ready: false },
  templateKindIndex: { exists: false, valid: false, ready: false },
  validationConstraint: { exists: false, validated: false },
  presentIndexesExact: true,
  validationConstraintExact: true,
  columnNotNull: false,
  transitionTriggerPresent: true,
  transitionContractExact: true,
};

const SESSION_ROW = {
  sessionRole: "meddoc",
  currentRole: "meddoc",
  database: "meddoc_lineage_test",
  serverAddress: "192.0.2.20",
  serverPort: 5432,
  serverVersionNumber: 160_013,
  systemIdentifier: "7623456789012345678",
  searchPath: "pg_catalog,public",
  statementTimeoutMs: 30_000,
  lockTimeoutMs: 2_000,
  applicationName: "quillmd_template_twin_lineage_online_v1",
  transactionReadOnly: "off",
  ssl: false,
  databaseOwner: "meddoc",
  principalCanLogin: true,
  principalSuperuser: true,
  inRecovery: false,
};

function sessionClient(
  overrides: Record<string, unknown> = {},
  rowOverrides: Record<string, unknown> = {},
): PoolClient {
  return {
    host: "postgres.internal",
    port: 5432,
    database: "meddoc_lineage_test",
    user: "meddoc",
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
        DATABASE_URL: databaseUrl,
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

describe("Template Twin lineage target-bound operator", () => {
  it("requires each CLI control at most once", () => {
    expect(() =>
      parseLineageOperatorArgs(["--phase", "status", "--phase", "backfill"]),
    ).toThrow("Duplicate argument: --phase");
  });

  it("uses canonical phase timeouts and server-enforced read-only status", () => {
    const base =
      "postgresql://meddoc:synthetic@postgres.internal:5432/meddoc_lineage_test?schema=public";
    const status = new URL(
      buildLineageOperatorConnectionString(base, "status"),
    );
    const indexes = new URL(
      buildLineageOperatorConnectionString(base, "indexes"),
    );
    expect(status.searchParams.getAll("options")).toEqual([
      "-c search_path=pg_catalog,public -c statement_timeout=30000 -c lock_timeout=2000 -c application_name=quillmd_template_twin_lineage_online_v1 -c default_transaction_read_only=on",
    ]);
    expect(indexes.searchParams.getAll("options")).toEqual([
      "-c search_path=pg_catalog,public -c statement_timeout=900000 -c lock_timeout=2000 -c application_name=quillmd_template_twin_lineage_online_v1 -c default_transaction_read_only=off",
    ]);
  });

  it.each([
    ["duplicate options", "&options=x&options=y"],
    ["query target override", "&host=alternate"],
    ["direct role", "&role=owner"],
    ["unknown transport input", "&synthetic_route=alternate"],
    ["wrong schema", "&schema=alternate"],
    ["surrounding whitespace", " "],
  ])("rejects noncanonical operator input: %s", (_label, suffix) => {
    const base =
      "postgresql://meddoc:synthetic@postgres.internal:5432/meddoc_lineage_test?schema=public";
    expect(() =>
      buildLineageOperatorConnectionString(`${base}${suffix}`, "backfill"),
    ).toThrow();
  });

  it("binds approval to target, system identity, phase, and protocol state", () => {
    const lowLevel = lineageOperatorTargetFingerprint(
      TARGET,
      "guard-index",
      STATUS.phase,
      "a".repeat(64),
    );
    expect(lowLevel).toMatch(/^[a-f0-9]{64}$/u);
    const approved = lineageOperatorApprovalFingerprint(
      TARGET,
      STATUS,
      "guard-index",
    );
    expect(() =>
      assertApprovedLineageOperatorTarget(
        TARGET,
        STATUS,
        "guard-index",
        approved,
      ),
    ).not.toThrow();
    expect(() =>
      assertApprovedLineageOperatorTarget(
        TARGET,
        STATUS,
        "guard-index",
        undefined,
      ),
    ).toThrow("LINEAGE_MIGRATION_TARGET_APPROVAL_REQUIRED");

    const alternatives = [
      {
        target: { ...TARGET, systemIdentifier: "7623456789012345679" },
        status: STATUS,
      },
      {
        target: { ...TARGET, serverAddress: "192.0.2.21" },
        status: STATUS,
      },
      { target: TARGET, status: { ...STATUS, phase: "GUARDED" as const } },
      { target: TARGET, status: { ...STATUS, rowsProcessed: 1 } },
    ];
    for (const alternative of alternatives) {
      expect(() =>
        assertApprovedLineageOperatorTarget(
          alternative.target,
          alternative.status,
          "guard-index",
          approved,
        ),
      ).toThrow("LINEAGE_MIGRATION_TARGET_APPROVAL_MISMATCH");
    }
    expect(() =>
      assertApprovedLineageOperatorTarget(
        { ...TARGET, inRecovery: true },
        STATUS,
        "guard-index",
        "a".repeat(64),
      ),
    ).toThrow("LINEAGE_MIGRATION_TARGET_IN_RECOVERY");
  });

  it("never emits the internal template cursor", () => {
    const output = lineageStatusForOutput({
      ...STATUS,
      lastProcessedId: "synthetic-template-identifier",
    });
    expect(output).not.toHaveProperty("lastProcessedId");
    expect(output.cursorPresent).toBe(true);
    expect(JSON.stringify(output)).not.toContain(
      "synthetic-template-identifier",
    );
  });

  it.each([
    ["client host", { host: "alternate.internal" }, {}],
    ["session login", {}, { sessionRole: "alternate" }],
    ["configured principal", { user: "meddoc_runtime" }, {}],
    ["database owner", {}, { databaseOwner: "alternate" }],
    ["principal login", {}, { principalCanLogin: false }],
    ["principal authority", {}, { principalSuperuser: false }],
    ["system identifier", {}, { systemIdentifier: "invalid" }],
    ["search path", {}, { searchPath: "public" }],
    ["statement timeout", {}, { statementTimeoutMs: 900_000 }],
    ["transaction mode", {}, { transactionReadOnly: "on" }],
  ])("rejects live %s drift", async (_label, clientOverrides, rowOverrides) => {
    await expect(
      preflightLineageOperatorTarget(
        sessionClient(clientOverrides, rowOverrides),
        {
          host: "postgres.internal",
          port: 5432,
          database: "meddoc_lineage_test",
          login: "meddoc",
        },
        "backfill",
      ),
    ).rejects.toThrow("LINEAGE_MIGRATION_SESSION_TARGET_MISMATCH");
  });

  it("returns the exact live target and reports recovery without minting trust", async () => {
    await expect(
      preflightLineageOperatorTarget(
        sessionClient({}, { inRecovery: true }),
        {
          host: "postgres.internal",
          port: 5432,
          database: "meddoc_lineage_test",
          login: "meddoc",
        },
        "backfill",
      ),
    ).resolves.toMatchObject({
      systemIdentifier: "7623456789012345678",
      inRecovery: true,
      tlsIdentity: "plaintext",
    });
  });

  it("runs BEGIN, work, and COMMIT on the one retained client", async () => {
    const calls: Array<{ query: string; values: unknown[] | undefined }> = [];
    const connection = {
      query: vi.fn(async (query: string, values?: unknown[]) => {
        calls.push({ query, values });
        return query === "SELECT synthetic"
          ? { rows: [{ value: 1 }], rowCount: 1 }
          : { rows: [], rowCount: 0 };
      }),
    } as unknown as PoolClient;
    const client = createLineageSessionClient(connection);
    const value = await client.$transaction(async (tx) => {
      return tx.$queryRawUnsafe<Array<{ value: number }>>(
        "SELECT synthetic",
        "bound",
      );
    });
    expect(value).toEqual([{ value: 1 }]);
    expect(calls.map((call) => call.query)).toEqual([
      "BEGIN",
      "SELECT synthetic",
      "COMMIT",
    ]);
    expect(calls[1]?.values).toEqual(["bound"]);
  });

  it("rolls back the same retained client on failure", async () => {
    const queries: string[] = [];
    const connection = {
      query: vi.fn(async (query: string) => {
        queries.push(query);
        return { rows: [], rowCount: 0 };
      }),
    } as unknown as PoolClient;
    const client = createLineageSessionClient(connection);
    await expect(
      client.$transaction(async () => {
        throw new Error("synthetic");
      }),
    ).rejects.toThrow("synthetic");
    expect(queries).toEqual(["BEGIN", "ROLLBACK"]);
  });

  it("prints only allowlisted failure codes", () => {
    expect(
      safeLineageOperatorErrorCode(
        new Error("SYNTHETIC_UPPERCASE_SECRET_SENTINEL"),
      ),
    ).toBe("LINEAGE_MIGRATION_OPERATOR_FAILED");
    expect(
      safeLineageOperatorErrorCode(
        new Error("LINEAGE_MIGRATION_TARGET_APPROVAL_REQUIRED"),
      ),
    ).toBe("LINEAGE_MIGRATION_TARGET_APPROVAL_REQUIRED");
    expect(
      safeLineageOperatorDiagnosticCode(
        Object.assign(new Error("synthetic-secret"), { code: "42601" }),
        "STATUS_SNAPSHOT",
      ),
    ).toBe("LINEAGE_MIGRATION_DATABASE_42601");
    expect(
      safeLineageOperatorDiagnosticCode(
        new Error("synthetic-secret"),
        "STATUS_SNAPSHOT",
      ),
    ).toBe("LINEAGE_MIGRATION_STATUS_SNAPSHOT_FAILED");
  });

  it.each([
    {
      label: "malformed URL",
      args: ["--phase", "status"],
      url: "postgresql://synthetic:synthetic-url-secret@[",
      sentinel: "synthetic-url-secret",
      expected: "LINEAGE_MIGRATION_CONNECTION_STRING_FAILED\n",
    },
    {
      label: "connection failure",
      args: ["--phase", "status"],
      url: "postgresql://synthetic:synthetic-connect-secret@127.0.0.1:1/meddoc_lineage_test?schema=public",
      sentinel: "synthetic-connect-secret",
      expected: "LINEAGE_MIGRATION_CONNECT_FAILED\n",
    },
    {
      label: "argument failure",
      args: ["--phase", "status", "--synthetic-argument-secret"],
      url: "postgresql://synthetic:synthetic-url-secret@127.0.0.1:1/meddoc_lineage_test?schema=public",
      sentinel: "synthetic-argument-secret",
      expected: "LINEAGE_MIGRATION_ARGUMENT_INVALID\n",
    },
  ])("redacts $label", async ({ args, url, sentinel, expected }) => {
    const result = await runOperator(args, url);
    expect(result.code).not.toBe(0);
    expect(result.stdout).toBe("");
    expect(result.stderr).toBe(expected);
    expect(`${result.stdout}${result.stderr}`).not.toContain(sentinel);
    expect(`${result.stdout}${result.stderr}`).not.toContain("password");
  });
});
