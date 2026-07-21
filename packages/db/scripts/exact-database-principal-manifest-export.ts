#!/usr/bin/env tsx

// Restricted evidence exporter for the frozen PostgreSQL 16 principal
// contract. It accepts only an explicitly acknowledged disposable database,
// emits no URL/catalog entry to stdout, and creates non-overwritable 0600
// files in an existing non-symlink directory.

import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import {
  constants,
  lstatSync,
  openSync,
  closeSync,
  writeFileSync,
} from "node:fs";

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";

import { assertNonProdDatabase } from "../src/db-guard";
import {
  type ExactPrincipalCatalogRow,
  exactDatabasePrincipalCatalogQuery,
} from "../src/exact-database-principal-query";
import { EXACT_DATABASE_PRINCIPAL_CONTRACT } from "../src/exact-database-principal";

const productionImageDigest =
  "pgvector/pgvector@sha256:7d400e340efb42f4d8c9c12c6427adb253f726881a9985d2a471bf0eed824dff";

const databaseUrl =
  process.env.EXACT_DATABASE_PRINCIPAL_MANIFEST_DATABASE_URL?.trim();
const outputDirectory =
  process.env.EXACT_DATABASE_PRINCIPAL_MANIFEST_OUTPUT_DIR?.trim();
const releaseSha =
  process.env.EXACT_DATABASE_PRINCIPAL_MANIFEST_RELEASE_SHA?.trim();
const imageDigest =
  process.env.EXACT_DATABASE_PRINCIPAL_MANIFEST_IMAGE_DIGEST?.trim();

if (!databaseUrl || !outputDirectory || !releaseSha || !imageDigest) {
  throw new Error("Exact manifest export inputs are required");
}
const target = assertNonProdDatabase(databaseUrl);
if (
  !/^meddoc_exact_principal_manifest_test_[a-z0-9_]+$/u.test(target.database)
) {
  throw new Error("Exact disposable manifest database name is required");
}
if (
  process.env.EXACT_DATABASE_PRINCIPAL_MANIFEST_CLUSTER_ACK !== target.database
) {
  throw new Error(
    "Exact disposable manifest cluster acknowledgement is required",
  );
}
if (!/^[0-9a-f]{40}$/u.test(releaseSha)) {
  throw new Error("Exact release SHA is required");
}
if (imageDigest !== productionImageDigest) {
  throw new Error("Pinned production PostgreSQL image digest is required");
}
const outputMetadata = lstatSync(outputDirectory);
if (!outputMetadata.isDirectory() || outputMetadata.isSymbolicLink()) {
  throw new Error("Restricted evidence directory must be a real directory");
}

const pairs = [
  ["meddoc_runtime", "quillmd_runtime"],
  ["meddoc_release_control", "quillmd_release_control"],
  ["meddoc_release_security", "quillmd_release_security"],
  ["meddoc_audit_dispatcher", "quillmd_audit_dispatcher"],
  ["meddoc_auth_email_dispatcher", "quillmd_auth_email_dispatcher"],
  ["meddoc_backup", "quillmd_backup"],
] as const;

type ManifestName =
  | "applicationAcl"
  | "applicationPublicAcl"
  | "systemPublicAcl"
  | "futureDefaultAcl";

const sharedManifestFields = {
  applicationAcl: [
    "applicationAclManifest",
    "applicationAclCount",
    "applicationAclSha256",
  ],
  applicationPublicAcl: [
    "applicationPublicAclManifest",
    "applicationPublicAclCount",
    "applicationPublicAclSha256",
  ],
  systemPublicAcl: [
    "systemPublicAclManifest",
    "systemPublicAclCount",
    "systemPublicAclSha256",
  ],
  futureDefaultAcl: [
    "futureDefaultAclManifest",
    "futureDefaultAclCount",
    "futureDefaultAclSha256",
  ],
} as const satisfies Record<
  ManifestName,
  readonly [
    keyof ExactPrincipalCatalogRow,
    keyof ExactPrincipalCatalogRow,
    keyof ExactPrincipalCatalogRow,
  ]
>;

function digest(entries: readonly string[]): string {
  return createHash("sha256").update(entries.join("\n"), "utf8").digest("hex");
}

function assertCanonicalManifest(input: {
  entries: unknown;
  count: unknown;
  sha256: unknown;
  label: string;
}): asserts input is {
  entries: string[];
  count: number;
  sha256: string;
  label: string;
} {
  assert(Array.isArray(input.entries), `${input.label} entries are required`);
  assert(
    input.entries.every((entry) => typeof entry === "string"),
    `${input.label} entries must be text`,
  );
  for (let index = 1; index < input.entries.length; index += 1) {
    assert(
      Buffer.compare(
        Buffer.from(input.entries[index - 1]!, "utf8"),
        Buffer.from(input.entries[index]!, "utf8"),
      ) <= 0,
      `${input.label} entries must use canonical C ordering`,
    );
  }
  assert.equal(input.entries.length, input.count, `${input.label} count`);
  assert.equal(digest(input.entries), input.sha256, `${input.label} digest`);
}

function createRestrictedFile(name: string, body: string): void {
  const path = `${outputDirectory}/${name}`;
  const descriptor = openSync(
    path,
    constants.O_CREAT |
      constants.O_EXCL |
      constants.O_WRONLY |
      constants.O_NOFOLLOW,
    0o600,
  );
  try {
    writeFileSync(descriptor, body, { encoding: "utf8" });
  } finally {
    closeSync(descriptor);
  }
}

function assertHardPredicates(row: ExactPrincipalCatalogRow): void {
  for (const field of [
    "boundaryHasPassword",
    "boundaryHasUnexpectedDependency",
    "graphHasForbiddenGrantor",
    "databaseHasGlobalRoleSettings",
    "hasApplicablePolicy",
    "hasPublicUserMapping",
    "hasBoundaryUserMapping",
    "hasForeignDataAuthority",
    "hasWritableApplicationSchema",
    "hasUnapprovedApplicationAuthority",
    "hasUnsafeExecutableCapability",
    "hasForbiddenLargeObjectFunctionAuthority",
    "hasLargeObjects",
    "hasForbiddenDatabaseAuthority",
  ] as const) {
    assert.equal(row[field], false, `${field} must be false`);
  }
  assert.equal(row.loginHasExactVerifier, true);
  assert.equal(row.readAllDataClosureIsExact, true);
  assert.equal(row.loginCanConnectCurrentDatabase, true);
  assert.equal(row.boundaryCanConnectCurrentDatabase, true);
  assert.equal(row.sessionSearchPath, "pg_catalog,public");
}

async function main(): Promise<void> {
  const shared = new Map<ManifestName, string[]>();
  const evidence: {
    contractVersion: "exact-database-principal-v9";
    releaseSha: string;
    postgresImageDigest: string;
    databaseName: string;
    boundaries: Record<string, { count: number; sha256: string; file: string }>;
    shared: Record<string, { count: number; sha256: string; file: string }>;
  } = {
    contractVersion: "exact-database-principal-v9",
    releaseSha,
    postgresImageDigest: imageDigest,
    databaseName: target.database,
    boundaries: {},
    shared: {},
  };

  for (const [loginRole, boundaryRole] of pairs) {
    const roleUrl = new URL(databaseUrl);
    roleUrl.username = loginRole;
    roleUrl.password = "";
    roleUrl.searchParams.set("options", "-c search_path=pg_catalog,public");
    const prisma = new PrismaClient({
      adapter: new PrismaPg({
        connectionString: roleUrl.toString(),
        connectionTimeoutMillis: 10_000,
      }),
    });
    try {
      const rows = await prisma.$queryRaw<ExactPrincipalCatalogRow[]>(
        exactDatabasePrincipalCatalogQuery({
          loginRole,
          boundaryRole,
          includeManifestEntries: true,
        }),
      );
      assert.equal(rows.length, 1);
      const row = rows[0]!;
      assertHardPredicates(row);

      assertCanonicalManifest({
        entries: row.boundaryAclManifest,
        count: row.boundaryAclCount,
        sha256: row.boundaryAclSha256,
        label: boundaryRole,
      });
      const expectedBoundary =
        EXACT_DATABASE_PRINCIPAL_CONTRACT.boundaries[
          boundaryRole as keyof typeof EXACT_DATABASE_PRINCIPAL_CONTRACT.boundaries
        ];
      if (expectedBoundary) {
        assert.equal(row.boundaryAclCount, expectedBoundary.count);
        assert.equal(row.boundaryAclSha256, expectedBoundary.sha256);
      }
      const boundaryFile = `boundary-${boundaryRole}.jsonl`;
      createRestrictedFile(boundaryFile, row.boundaryAclManifest.join("\n"));
      evidence.boundaries[boundaryRole] = {
        count: row.boundaryAclCount,
        sha256: row.boundaryAclSha256,
        file: boundaryFile,
      };

      for (const [
        name,
        [entriesField, countField, digestField],
      ] of Object.entries(sharedManifestFields) as Array<
        [ManifestName, (typeof sharedManifestFields)[ManifestName]]
      >) {
        const entries = row[entriesField];
        const count = row[countField];
        const sha256 = row[digestField];
        assertCanonicalManifest({ entries, count, sha256, label: name });
        const prior = shared.get(name);
        if (prior) {
          assert.deepEqual(entries, prior, `${name} must match every profile`);
        } else {
          shared.set(name, entries);
        }
      }
    } finally {
      await prisma.$disconnect();
    }
  }

  for (const [name, entries] of shared) {
    const file = `shared-${name}.jsonl`;
    const sha256 = digest(entries);
    createRestrictedFile(file, entries.join("\n"));
    evidence.shared[name] = { count: entries.length, sha256, file };
  }
  assert.equal(
    evidence.shared.applicationAcl?.count,
    EXACT_DATABASE_PRINCIPAL_CONTRACT.applicationAclCount,
  );
  assert.equal(
    evidence.shared.applicationAcl?.sha256,
    EXACT_DATABASE_PRINCIPAL_CONTRACT.applicationAclSha256,
  );
  assert.equal(
    evidence.shared.applicationPublicAcl?.count,
    EXACT_DATABASE_PRINCIPAL_CONTRACT.applicationPublicAclCount,
  );
  assert.equal(
    evidence.shared.applicationPublicAcl?.sha256,
    EXACT_DATABASE_PRINCIPAL_CONTRACT.applicationPublicAclSha256,
  );
  assert.equal(
    evidence.shared.systemPublicAcl?.count,
    EXACT_DATABASE_PRINCIPAL_CONTRACT.systemPublicAclCount,
  );
  assert.equal(
    evidence.shared.systemPublicAcl?.sha256,
    EXACT_DATABASE_PRINCIPAL_CONTRACT.systemPublicAclSha256,
  );
  assert.equal(
    evidence.shared.futureDefaultAcl?.count,
    EXACT_DATABASE_PRINCIPAL_CONTRACT.futureDefaultAclCount,
  );
  assert.equal(
    evidence.shared.futureDefaultAcl?.sha256,
    EXACT_DATABASE_PRINCIPAL_CONTRACT.futureDefaultAclSha256,
  );
  createRestrictedFile(
    "manifest-index.json",
    `${JSON.stringify(evidence, null, 2)}\n`,
  );
  process.stdout.write("EXACT_DATABASE_PRINCIPAL_MANIFEST_EXPORT_PASS\n");
}

void main().catch(() => {
  process.stderr.write("EXACT_DATABASE_PRINCIPAL_MANIFEST_EXPORT_FAIL\n");
  process.exitCode = 1;
});
