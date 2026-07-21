import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const repositoryRoot = resolve(process.cwd(), "../..");
const v4 = readFileSync(
  resolve(
    repositoryRoot,
    "packages/db/prisma/migrations/20260720123000_template_twin_production_control_plane_mfa_hardening_v4/migration.sql",
  ),
  "utf8",
);
const v6 = readFileSync(
  resolve(
    repositoryRoot,
    "packages/db/prisma/migrations/20260720170000_auth_email_outbox_and_dispatcher_v6/migration.sql",
  ),
  "utf8",
);
const v6PgHarness = readFileSync(
  resolve(
    repositoryRoot,
    "packages/db/scripts/auth-email-role-graph-migration-pg-test.ts",
  ),
  "utf8",
);
const v9 = readFileSync(
  resolve(
    repositoryRoot,
    "packages/db/prisma/migrations/20260720213000_exact_database_principal_closure_v9/migration.sql",
  ),
  "utf8",
);
const v9PgHarness = readFileSync(
  resolve(
    repositoryRoot,
    "packages/db/scripts/exact-database-principal-pg-test.ts",
  ),
  "utf8",
);

describe("data-bearing database role graph guards", () => {
  it("makes v4 require the exact three-login/four-boundary graph", () => {
    for (const role of [
      "meddoc_runtime",
      "meddoc_release_control",
      "meddoc_audit_dispatcher",
      "quillmd_runtime",
      "quillmd_release_control",
      "quillmd_release_security",
      "quillmd_audit_dispatcher",
    ]) {
      expect(v4).toContain(role);
    }
    expect(v4).toContain("membership.member = member_role.oid");
    expect(v4).toContain("membership.roleid = boundary_role.oid");
    expect(v4).toContain("membership.admin_option = TRUE");
    expect(v4).toContain("membership.inherit_option = FALSE");
    expect(v4).toContain("membership.set_option = TRUE");
    expect(v4).toContain("meddoc_release_security");
    expect(v4).toMatch(
      /member_role\.rolname IN \([\s\S]*?'quillmd_runtime'[\s\S]*?\) OR granted_role\.rolname IN/u,
    );
    expect(v4).toMatch(
      /granted_role\.rolname IN \([\s\S]*?'meddoc_audit_dispatcher'[\s\S]*?'quillmd_runtime'/u,
    );
  });

  it("makes v6 require the exact four-login/five-boundary graph", () => {
    for (const role of [
      "meddoc_runtime",
      "meddoc_release_control",
      "meddoc_audit_dispatcher",
      "meddoc_auth_email_dispatcher",
      "quillmd_runtime",
      "quillmd_release_control",
      "quillmd_release_security",
      "quillmd_audit_dispatcher",
      "quillmd_auth_email_dispatcher",
    ]) {
      expect(v6).toContain(role);
    }
    expect(v6).not.toContain("CREATE ROLE quillmd_auth_email_dispatcher");
    expect(v6).toContain("membership.member = member_role.oid");
    expect(v6).toContain("membership.roleid = boundary_role.oid");
    expect(v6).toContain("membership.admin_option = TRUE");
    expect(v6).toContain("membership.inherit_option = FALSE");
    expect(v6).toContain("membership.set_option = TRUE");
    expect(v6).toContain("meddoc_release_security");
    expect(v6).toMatch(
      /granted_role\.rolname IN \([\s\S]*?'meddoc_auth_email_dispatcher'[\s\S]*?'quillmd_runtime'/u,
    );
    expect(v6).toContain(
      "Refusing non-exact auth email dispatcher database role graph",
    );
    expect(v6PgHarness).toContain("assertV6DispatcherSessionRoleGraph");
    expect(v6PgHarness).not.toContain("assertExactDatabasePrincipal");
    expect(v6PgHarness).toContain(
      "the v9 PostgreSQL harness owns final startup proof",
    );
  });

  it("keeps v9 structural and runs the full manifest as the immediate external gate", () => {
    expect(v9).toContain("DO $exact_role_graph$");
    expect(v9).toContain("DO $exact_helper_contract$");
    expect(v9).toContain("callable.prosrc");
    expect(v9).toContain("pg_catalog.aclexplode(callable.proacl)");
    expect(v9).toContain("pg_catalog.pg_shdepend dependency");
    expect(v9).not.toContain("applicationAclSha256");
    expect(v9).not.toContain("PREPARE quillmd_exact_principal_v9");
    expect(v9).not.toContain(
      "94e6070438f9bf644daa16ef722bf4f6431eadb06397bd295f3c3e71e194c97f",
    );
    expect(v9PgHarness).toMatch(
      /await admin\.query\(migrationSql\);[\s\S]{0,300}?await expectRuntimeAccepted\(\);/u,
    );
    expect(v9PgHarness).toContain(
      "embedding its deparse manifest under migration SQL is not stable",
    );
  });
});
