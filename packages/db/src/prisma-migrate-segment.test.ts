import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  PRISMA_MIGRATION_SEGMENTS,
  assertExactLedgerPrefix,
  assertMigrationNetworkTargetBoundary,
  databaseReleaseMigrationApprovalFingerprint,
  buildMigrationDeployConnectionString,
  buildMigrationProbeConnectionString,
  buildPrismaMigrationInvocation,
  buildPrismaMigrationChildEnvironment,
  classifyPrismaMigrationFailure,
  normalizePrismaLedgerAttempts,
  parsePrismaMigrationSegmentArgs,
  readExactMigrationSources,
  resolveMigrationTimeoutContract,
} from "../scripts/prisma-migrate-segment";

const TARGET =
  "postgresql://meddoc:synthetic@postgres:5432/meddoc_qa_test?schema=public";

describe("closed segmented Prisma migration runner", () => {
  it("accepts only the four reviewed cumulative phases and read-only status", () => {
    for (const phase of [
      "status",
      "lineage-expand",
      "auth-expand",
      "pre-v9",
      "v9",
    ]) {
      expect(parsePrismaMigrationSegmentArgs(["--phase", phase])).toBe(phase);
    }
    for (const args of [
      [],
      ["--phase"],
      ["--phase", "all"],
      ["--phase", "68"],
      ["--cutoff", "20260715162000_template_twin_docx_v1"],
      ["--phase", "v9", "--force"],
    ]) {
      expect(() => parsePrismaMigrationSegmentArgs(args)).toThrow(
        /DATABASE_RELEASE_MIGRATION_PHASE/u,
      );
    }
  });

  it("binds the exact 97-source history to every fixed cutoff", () => {
    const sources = readExactMigrationSources();
    expect(sources).toHaveLength(97);
    for (const segment of Object.values(PRISMA_MIGRATION_SEGMENTS)) {
      expect(sources[segment.count - 1]?.name).toBe(segment.lastMigration);
    }
    expect(
      Object.values(PRISMA_MIGRATION_SEGMENTS).map(({ count }) => count),
    ).toEqual([68, 93, 96, 97]);
  });

  it("binds mutation approval to target, phase, ledger, and source cutoff", () => {
    const sources = readExactMigrationSources();
    const ledger = sources.slice(0, 68).map((source) => ({
      migrationName: source.name,
      checksum: source.checksum,
    }));
    const approved = databaseReleaseMigrationApprovalFingerprint({
      targetFingerprint: "a".repeat(64),
      phase: "auth-expand",
      ledger,
      sources,
    });
    expect(approved).toMatch(/^[a-f0-9]{64}$/u);
    for (const drift of [
      { targetFingerprint: "b".repeat(64), phase: "auth-expand" as const },
      { targetFingerprint: "a".repeat(64), phase: "lineage-expand" as const },
    ]) {
      expect(
        databaseReleaseMigrationApprovalFingerprint({
          ...drift,
          ledger,
          sources,
        }),
      ).not.toBe(approved);
    }
    expect(
      databaseReleaseMigrationApprovalFingerprint({
        targetFingerprint: "a".repeat(64),
        phase: "auth-expand",
        ledger: ledger.slice(0, -1),
        sources,
      }),
    ).not.toBe(approved);
    expect(
      databaseReleaseMigrationApprovalFingerprint({
        targetFingerprint: "a".repeat(64),
        phase: "auth-expand",
        ledger,
        sources: sources.map((source, index) =>
          index === 80 ? { ...source, checksum: "f".repeat(64) } : source,
        ),
      }),
    ).not.toBe(approved);
  });

  it("binds probe and deploy connections to the reviewed finite timeouts", () => {
    const environment = {
      PRISMA_STATEMENT_TIMEOUT_MS: "180000",
      DATABASE_RELEASE_MIGRATION_LOCK_TIMEOUT_MS: "5000",
    };
    expect(resolveMigrationTimeoutContract(environment)).toEqual({
      statementTimeoutMs: 180_000,
      lockTimeoutMs: 5_000,
    });

    const status = new URL(
      buildMigrationProbeConnectionString({
        databaseUrl: TARGET,
        phase: "status",
        environment,
      }),
    );
    expect(status.searchParams.get("options")).toBe(
      "-c search_path=pg_catalog,public -c statement_timeout=180000 -c lock_timeout=5000 -c application_name=quillmd_prisma_migrate_segment_probe_v1 -c default_transaction_read_only=on",
    );

    const deploy = new URL(
      buildMigrationDeployConnectionString({
        databaseUrl: TARGET,
        environment,
      }),
    );
    expect(deploy.username).toBe("meddoc");
    expect(deploy.password).toBe("synthetic");
    expect(deploy.searchParams.get("options")).toBe(
      "-c search_path=pg_catalog,public -c statement_timeout=180000 -c lock_timeout=5000 -c application_name=quillmd_prisma_migrate_segment_deploy_v1",
    );
  });

  it("requires the Compose-shared PostgreSQL loopback namespace for mutation", () => {
    const valid = {
      databaseUrl:
        "postgresql://meddoc:synthetic@127.0.0.1:5432/meddoc_qa_test?schema=public",
      clientAddress: "127.0.0.1",
      serverAddress: "127.0.0.1",
      environment: {
        DATABASE_RELEASE_MIGRATION_NETWORK_BOUNDARY: "postgres-loopback-v1",
      },
    };
    expect(() => assertMigrationNetworkTargetBoundary(valid)).not.toThrow();
    for (const drift of [
      { ...valid, databaseUrl: TARGET },
      { ...valid, clientAddress: "172.18.0.3" },
      { ...valid, serverAddress: "172.18.0.2" },
      { ...valid, environment: {} },
    ]) {
      expect(() => assertMigrationNetworkTargetBoundary(drift)).toThrow(
        "DATABASE_RELEASE_MIGRATION_NETWORK_BOUNDARY_INVALID",
      );
    }
  });

  it("passes only the target-bound URL and fixed Prisma controls to the child", () => {
    const environment = {
      PATH: "/synthetic/bin",
      CI: "true",
      DATABASE_URL: "postgresql://must-not-leak",
      DATABASE_RELEASE_MIGRATION_APPROVED_TARGET_FINGERPRINT: "f".repeat(64),
      UNRELATED_SECRET: "must-not-leak",
    };
    const child = buildPrismaMigrationChildEnvironment(TARGET, environment);
    expect(child).toEqual({
      PATH: "/synthetic/bin",
      DATABASE_URL: TARGET,
      CI: "true",
      NO_COLOR: "1",
      PRISMA_HIDE_UPDATE_MESSAGE: "1",
    });
  });

  it("invokes the exact installed Prisma entry point without an npm wrapper", () => {
    const invocation = buildPrismaMigrationInvocation(
      "/tmp/quillmd-reviewed-prisma.config.ts",
    );
    expect(invocation.executable).toBe(process.execPath);
    expect(invocation.args).toEqual([
      expect.stringMatching(/\/node_modules\/prisma\/build\/index\.js$/u),
      "migrate",
      "deploy",
      "--config",
      "/tmp/quillmd-reviewed-prisma.config.ts",
    ]);
    expect(
      `${invocation.executable}\n${invocation.args.join("\n")}`,
    ).not.toMatch(/(?:^|\/)npx(?:$|\s)/u);
    const source = readFileSync(
      resolve(__dirname, "../scripts/prisma-migrate-segment.ts"),
      "utf8",
    );
    expect(source).toContain(
      "const invocation = buildPrismaMigrationInvocation(configPath);",
    );
    expect(source).not.toMatch(/spawnSync\(\s*["']npx["']/u);
  });

  it("classifies Prisma child failures without reflecting diagnostic values", () => {
    const sensitive =
      "postgresql://meddoc:synthetic-sensitive-value@127.0.0.1:5432/meddoc_ci_test";
    const classify = (input: {
      error?: NodeJS.ErrnoException;
      status?: number | null;
      signal?: NodeJS.Signals | null;
      stdout?: string;
      stderr?: string;
    }) =>
      classifyPrismaMigrationFailure({
        status: 1,
        signal: null,
        stdout: "",
        stderr: sensitive,
        ...input,
      });

    const cases = [
      [
        classify({
          error: Object.assign(new Error(sensitive), { code: "ETIMEDOUT" }),
        }),
        "DATABASE_RELEASE_MIGRATION_PRISMA_PROCESS_TIMEOUT",
      ],
      [
        classify({
          error: Object.assign(new Error(sensitive), { code: "ENOBUFS" }),
        }),
        "DATABASE_RELEASE_MIGRATION_PRISMA_OUTPUT_LIMIT",
      ],
      [
        classify({
          error: Object.assign(new Error(sensitive), { code: "ENOMEM" }),
        }),
        "DATABASE_RELEASE_MIGRATION_PRISMA_RESOURCE_EXHAUSTED",
      ],
      [
        classify({
          error: Object.assign(new Error(sensitive), { code: "ENOENT" }),
        }),
        "DATABASE_RELEASE_MIGRATION_PRISMA_PROCESS_START_FAILED",
      ],
      [
        classify({ signal: "SIGKILL" }),
        "DATABASE_RELEASE_MIGRATION_PRISMA_PROCESS_TERMINATED",
      ],
      [
        classify({ status: 137, stderr: `Killed ${sensitive}` }),
        "DATABASE_RELEASE_MIGRATION_PRISMA_PROCESS_TERMINATED",
      ],
      [
        classify({ status: 143, stderr: sensitive }),
        "DATABASE_RELEASE_MIGRATION_PRISMA_PROCESS_TERMINATED",
      ],
      [
        classify({ stderr: `55P03 lock timeout ${sensitive}` }),
        "DATABASE_RELEASE_MIGRATION_PRISMA_LOCK_TIMEOUT",
      ],
      [
        classify({ stderr: `57014 statement timeout ${sensitive}` }),
        "DATABASE_RELEASE_MIGRATION_PRISMA_STATEMENT_TIMEOUT",
      ],
      [
        classify({
          stdout: `P3009 previous P3018 statement timeout ${sensitive}`,
        }),
        "DATABASE_RELEASE_MIGRATION_PRISMA_LEDGER_BLOCKED",
      ],
      [
        classify({ stderr: `P3018 ${sensitive}` }),
        "DATABASE_RELEASE_MIGRATION_PRISMA_APPLY_FAILED",
      ],
      [
        classify({ stderr: `P2024 ${sensitive}` }),
        "DATABASE_RELEASE_MIGRATION_PRISMA_KNOWN_ERROR",
      ],
      [
        classify({ stderr: sensitive }),
        "DATABASE_RELEASE_MIGRATION_PRISMA_FAILED",
      ],
    ] as const;

    for (const [actual, expected] of cases) {
      expect(actual).toBe(expected);
      expect(actual).not.toContain(sensitive);
    }
  });

  it.each([
    { PRISMA_STATEMENT_TIMEOUT_MS: "0" },
    { DATABASE_RELEASE_MIGRATION_LOCK_TIMEOUT_MS: "0" },
    { DATABASE_RELEASE_MIGRATION_LOCK_TIMEOUT_MS: "5s" },
  ])("rejects an unsafe migration timeout contract", (environment) => {
    expect(() => resolveMigrationTimeoutContract(environment)).toThrow(
      "DATABASE_CONNECTION_OPTIONS_INVALID",
    );
  });

  it("accepts only a successful official-checksum ledger prefix", () => {
    const sources = readExactMigrationSources();
    const valid = sources.slice(0, 2).map((migration) => ({
      migrationName: migration.name,
      checksum: migration.checksum,
      finished: true,
      notRolledBack: true,
      appliedStepsCount: 1,
    }));
    expect(() => assertExactLedgerPrefix(valid, sources)).not.toThrow();

    for (const drift of [
      [{ ...valid[0]!, checksum: "0".repeat(64) }, valid[1]!],
      [{ ...valid[0]!, finished: false }, valid[1]!],
      [{ ...valid[0]!, notRolledBack: false }, valid[1]!],
      [{ ...valid[0]!, appliedStepsCount: 0 }, valid[1]!],
      [valid[1]!, valid[0]!],
    ]) {
      expect(() => assertExactLedgerPrefix(drift, sources)).toThrow();
    }
  });

  it("retains resolved failures as evidence while normalizing only successful rows", () => {
    const sources = readExactMigrationSources();
    const first = sources[0]!;
    const second = sources[1]!;
    const attempts = [
      {
        id: "attempt-1",
        migrationName: first.name,
        checksum: first.checksum,
        finished: false,
        rolledBack: true,
        appliedStepsCount: 0,
      },
      {
        id: "attempt-2",
        migrationName: first.name,
        checksum: first.checksum,
        finished: true,
        rolledBack: false,
        appliedStepsCount: 1,
      },
      {
        id: "attempt-3",
        migrationName: second.name,
        checksum: second.checksum,
        finished: false,
        rolledBack: true,
        appliedStepsCount: 0,
      },
    ];
    expect(normalizePrismaLedgerAttempts(attempts, sources)).toEqual([
      {
        migrationName: first.name,
        checksum: first.checksum,
        finished: true,
        notRolledBack: true,
        appliedStepsCount: 1,
      },
    ]);

    for (const drift of [
      [{ ...attempts[0]!, rolledBack: false }],
      [{ ...attempts[0]!, finished: true }],
      [{ ...attempts[0]!, checksum: "0".repeat(64) }],
      [attempts[1]!, { ...attempts[1]!, id: "duplicate-success" }],
      [
        attempts[1]!,
        {
          ...attempts[2]!,
          migrationName: sources[2]!.name,
          checksum: sources[2]!.checksum,
        },
      ],
    ]) {
      expect(() => normalizePrismaLedgerAttempts(drift, sources)).toThrow();
    }
  });
});
