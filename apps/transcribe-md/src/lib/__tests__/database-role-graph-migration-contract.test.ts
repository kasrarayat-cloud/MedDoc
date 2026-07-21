import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const repositoryRoot = resolve(import.meta.dirname, "../../../../..");
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
const e2eWorkflow = readFileSync(
  resolve(repositoryRoot, ".github/workflows/e2e.yml"),
  "utf8",
);

describe("data-bearing database role graph guards", () => {
  it("generates isolated strong CI database credentials before Compose parsing", () => {
    const credentialProvisioning = e2eWorkflow.indexOf(
      "- name: Provision ephemeral synthetic database credentials",
    );
    const imageBuild = e2eWorkflow.indexOf("- name: Build app + worker images");

    expect(credentialProvisioning).toBeGreaterThan(-1);
    expect(imageBuild).toBeGreaterThan(credentialProvisioning);
    const provisioning = e2eWorkflow.slice(credentialProvisioning, imageBuild);
    expect(provisioning).toContain('randomBytes(32).toString("base64url")');
    expect(provisioning).toContain(
      "writeFileSync(backupPath, qa.backup, { mode: 0o444 });",
    );
    expect(provisioning).toContain('install -d -m 0700 "$credential_dir"');
    expect(provisioning).toContain('chmod 0444 "$backup_path"');
    expect(provisioning).toContain("{ mode: 0o600 }");
    for (const name of [
      "QA_DB_RUNTIME_PASSWORD",
      "QA_DB_RELEASE_CONTROL_PASSWORD",
      "QA_DB_RELEASE_SECURITY_PASSWORD",
      "QA_DB_AUDIT_DISPATCHER_PASSWORD",
      "QA_DB_AUTH_EMAIL_DISPATCHER_PASSWORD",
      "QA_DB_BACKUP_PASSWORD_FILE",
      "DB_RUNTIME_PASSWORD",
      "DB_RELEASE_CONTROL_PASSWORD",
      "DB_AUDIT_DISPATCHER_PASSWORD",
      "DB_AUTH_EMAIL_DISPATCHER_PASSWORD",
      "DB_BACKUP_PASSWORD_FILE",
    ]) {
      expect(provisioning).toContain(name);
    }
    expect(provisioning).not.toContain("qa_test_pw");
  });

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

  it("runs only the witnessed segmented migration order before runtime startup", () => {
    const lineageExpand = e2eWorkflow.indexOf(
      "- name: Apply lineage-expand migration segment",
    );
    const lineageContract = e2eWorkflow.indexOf(
      "- name: Contract NoteTemplate lineage in disposable QA",
    );
    const authExpand = e2eWorkflow.indexOf(
      "- name: Apply auth-expand migration segment",
    );
    const tokenLinearization = e2eWorkflow.indexOf(
      "- name: Complete auth-token linearization in disposable QA",
    );
    const preV9 = e2eWorkflow.indexOf("- name: Apply pre-v9 migration segment");
    const releaseSecurityProvision = e2eWorkflow.indexOf(
      "- name: Provision release-security principal in disposable QA",
    );
    const v9 = e2eWorkflow.indexOf(
      "- name: Apply exact-principal v9 migration segment",
    );
    const exactPrincipal = e2eWorkflow.indexOf(
      "- name: Prove every exact database principal after fresh migration",
    );
    const runtimeStartup = e2eWorkflow.indexOf("- name: Start app + worker");

    expect(lineageExpand).toBeGreaterThan(-1);
    expect(lineageContract).toBeGreaterThan(lineageExpand);
    expect(authExpand).toBeGreaterThan(lineageContract);
    expect(tokenLinearization).toBeGreaterThan(authExpand);
    expect(preV9).toBeGreaterThan(tokenLinearization);
    expect(releaseSecurityProvision).toBeGreaterThan(preV9);
    expect(v9).toBeGreaterThan(releaseSecurityProvision);
    expect(exactPrincipal).toBeGreaterThan(v9);
    expect(runtimeStartup).toBeGreaterThan(exactPrincipal);

    const lineageSegment = e2eWorkflow.slice(lineageExpand, lineageContract);
    expect(lineageSegment).toContain("--phase status");
    expect(lineageSegment).toContain(".appliedMigrations == 0");
    expect(lineageSegment).toContain("--phase lineage-expand");
    expect(lineageSegment).toContain(
      "DATABASE_RELEASE_MIGRATION_APPROVED_TARGET_FINGERPRINT",
    );

    const lineageGate = e2eWorkflow.slice(lineageContract, authExpand);
    expect(lineageGate).toContain("--phase status");
    expect(lineageGate).toContain(".targetFingerprints[$phase]");
    expect(lineageGate).toContain(
      "TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT",
    );
    expect(
      lineageGate.match(
        /-e TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT/gu,
      ),
    ).toHaveLength(6);
    expect(lineageGate).toContain("--phase guard-index");
    expect(lineageGate.match(/--phase backfill/gu)).toHaveLength(2);
    expect(lineageGate).toContain("--phase indexes");
    expect(lineageGate).toContain("--phase validate");
    expect(lineageGate).toContain("TEMPLATE_TWIN_LINEAGE_CONTRACT_ACK");
    expect(lineageGate).toContain("--phase contract");
    expect(lineageGate).toContain('.phase == "CONTRACTED"');
    expect(lineageGate).toContain(".partialIndex.exists == false");
    expect(lineageGate).toContain(".presentIndexesExact == true");
    expect(lineageGate).toContain(".validationConstraintExact == true");
    expect(lineageGate).toContain(".transitionContractExact == true");

    const authSegment = e2eWorkflow.slice(authExpand, tokenLinearization);
    expect(authSegment).toContain(".appliedMigrations == 68");
    expect(authSegment).toContain("--phase auth-expand");
    expect(authSegment).toContain("20260715162000_template_twin_docx_v1");

    const tokenGate = e2eWorkflow.slice(tokenLinearization, preV9);
    expect(tokenGate).toContain("--phase status");
    expect(tokenGate).toContain(".targetFingerprints.all");
    expect(tokenGate).toContain(
      "AUTH_TOKEN_LINEARIZATION_APPROVED_TARGET_FINGERPRINT",
    );
    expect(tokenGate).toContain("for attempt in 1 2");
    expect(tokenGate).toContain(
      "-- --phase all --batch-size 100 --batch-delay-ms 0",
    );
    expect(tokenGate).not.toMatch(/--\s*\n\s+--phase all/u);
    expect(tokenGate).toContain('.transitionTriggerState == "absent"');
    expect(tokenGate).toContain(".complete == true");

    const preV9Segment = e2eWorkflow.slice(preV9, releaseSecurityProvision);
    expect(preV9Segment).toContain(".appliedMigrations == 93");
    expect(preV9Segment).toContain("--phase pre-v9");
    expect(preV9Segment).toContain(
      "20260720150000_auth_token_linearization_v5",
    );

    const releaseSecurityGate = e2eWorkflow.slice(releaseSecurityProvision, v9);
    expect(releaseSecurityGate).toContain("pg_control_system()");
    expect(releaseSecurityGate).toContain(
      'DB_EXPECTED_SYSTEM_IDENTIFIER="$system_identifier"',
    );
    expect(releaseSecurityGate).toContain("-e DB_RELEASE_SECURITY_PASSWORD");
    expect(releaseSecurityGate).toContain(
      "infra/postgres/provision-template-twin-release-security.sh",
    );

    const v9Segment = e2eWorkflow.slice(v9, exactPrincipal);
    expect(v9Segment).toContain(".appliedMigrations == 96");
    expect(v9Segment).toContain("--phase v9");
    expect(v9Segment).toContain(
      "20260720200000_mfa_credential_lifecycle_audit_v8",
    );

    const gate = e2eWorkflow.slice(exactPrincipal, runtimeStartup);
    expect(gate).toContain("--no-deps");
    expect(gate).toContain("--entrypoint sh db-migrate");
    for (const profile of [
      "runtime",
      "release-control",
      "release-security",
      "audit-dispatcher",
      "auth-email-dispatcher",
      "backup",
    ]) {
      expect(gate).toContain(profile);
    }
    for (const login of [
      "meddoc_runtime",
      "meddoc_release_control",
      "meddoc_release_security",
      "meddoc_audit_dispatcher",
      "meddoc_auth_email_dispatcher",
      "meddoc_backup",
    ]) {
      expect(gate).toContain(login);
    }
    expect(gate).toContain("-e EXACT_DATABASE_PRINCIPAL_DATABASE_URL");
    expect(gate).toContain("-e EXACT_DATABASE_PRINCIPAL_PROFILE");
    expect(gate).toContain("database-principal:preflight -w @meddoc/db");

    expect(e2eWorkflow).not.toMatch(/run --rm(?: -T)? db-migrate\s*(?:\n|$)/u);
    expect(e2eWorkflow).not.toContain("prisma migrate deploy");
  });
});
