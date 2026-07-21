import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const repositoryRoot = resolve(process.cwd(), "../..");

function source(path: string): string {
  return readFileSync(resolve(repositoryRoot, path), "utf8");
}

const generator = source(
  "packages/db/scripts/generate-exact-database-principal-v9.ts",
);
const migration = source(
  "packages/db/prisma/migrations/20260720213000_exact_database_principal_closure_v9/migration.sql",
);
const query = source("packages/db/src/exact-database-principal-query.ts");
const verifier = source("packages/db/src/exact-database-principal.ts");
const bootstrap = source("infra/postgres/init-template-twin-roles.sh");
const provisioner = source(
  "infra/postgres/provision-postgres-backup-principal.sh",
);
const preflight = source(
  "infra/postgres-backup/hooks/10-principal-preflight",
);
const exactPgHarness = source(
  "packages/db/scripts/exact-database-principal-pg-test.ts",
);
const backupPgHarness = source(
  "packages/db/scripts/postgres-backup-principal-pg-test.ts",
);

describe("backup predefined-role and credential closure", () => {
  it("keeps generated v9 bytes synchronized around the trusted closure", () => {
    const expectedRole =
      "('pg_read_all_data', TRUE, FALSE, TRUE, FALSE, -1,";
    for (const artifact of [generator, migration]) {
      expect(artifact).toContain(expectedRole);
      expect(artifact).toContain(
        "('quillmd_backup', 'pg_read_all_data', TRUE, FALSE, TRUE, FALSE)",
      );
      expect(artifact).toMatch(
        /controlled_roles CONSTANT TEXT\[\][\s\S]*?'pg_read_all_data'/u,
      );
      expect(artifact).toContain("SCRAM-SHA-256$4096:%");
    }
  });

  it("attests verifier shape and the predefined-role closure at runtime", () => {
    expect(query).toContain('AS "loginHasExactVerifier"');
    expect(query).toContain('AS "readAllDataClosureIsExact"');
    expect(query).toContain("membership.member = read_all_data.oid");
    expect(query).toContain("membership.roleid = read_all_data.oid");
    expect(query).toContain("membership.grantor = read_all_data.oid");
    expect(verifier).toContain("principal.loginHasExactVerifier !== true");
    expect(verifier).toContain("principal.readAllDataClosureIsExact !== true");
  });

  it("enforces the same closure at bootstrap, provisioning, and backup admission", () => {
    for (const artifact of [bootstrap, provisioner, preflight]) {
      expect(artifact).toContain("role.rolname = 'pg_read_all_data'");
      expect(artifact).toContain("granted_role.rolname = 'pg_read_all_data'");
      expect(artifact).toContain("member_role.rolname = 'quillmd_backup'");
    }
    for (const artifact of [provisioner, preflight]) {
      expect(artifact).toContain(
        "'meddoc_backup', 'quillmd_backup', 'pg_read_all_data'",
      );
    }
    expect(provisioner).toContain(
      "quillmd_boundary_password_is_null('meddoc_backup')",
    );
    expect(provisioner).toContain("role.rolname = 'meddoc_backup'");
    expect(provisioner).toContain("login_result := TRUE");
    expect(preflight).toContain("('meddoc_backup')");
    expect(preflight).toContain("semantic_sha256");
  });

  it("keeps actual-PostgreSQL downgrade and transitive-closure regressions", () => {
    expect(exactPgHarness).toContain("login verifier downgrade");
    expect(exactPgHarness).toContain(
      "predefined read-role outgoing membership",
    );
    expect(backupPgHarness).toContain("readClosureProvision");
    expect(backupPgHarness).toContain("downgradedVerifierProvision");
  });
});
