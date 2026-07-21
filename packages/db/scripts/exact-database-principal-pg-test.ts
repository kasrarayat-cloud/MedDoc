#!/usr/bin/env tsx

// Actual-PostgreSQL 16 adversarial proof for the exact principal/catalog
// contract and additive v9 closure. The caller must provide one disposable,
// fully migrated isolated database; no ambient or production URL is accepted.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";
import { Client } from "pg";

import { assertNonProdDatabase } from "../src/db-guard";
import { assertExactDatabasePrincipal } from "../src/exact-database-principal";

const databaseUrl =
  process.env.EXACT_DATABASE_PRINCIPAL_TEST_DATABASE_URL?.trim();
if (!databaseUrl) {
  throw new Error("Disposable exact-principal database URL is required");
}
const target = assertNonProdDatabase(databaseUrl);
if (
  !/^meddoc_exact_principal_(?:fresh|v9)_test(?:_[a-z0-9_]+)?$/u.test(
    target.database,
  )
) {
  throw new Error("Exact disposable database name is required");
}
if (process.env.EXACT_DATABASE_PRINCIPAL_TEST_CLUSTER_ACK !== target.database) {
  throw new Error("Exact disposable cluster acknowledgement is required");
}

const migrationSql = readFileSync(
  fileURLToPath(
    new URL(
      "../prisma/migrations/20260720213000_exact_database_principal_closure_v9/migration.sql",
      import.meta.url,
    ),
  ),
  "utf8",
);
const quotedDatabase = `"${target.database.replaceAll('"', '""')}"`;
let diagnosticStage = "startup";
let diagnosticContext = "baseline";

function principalClient(
  loginRole = "meddoc_runtime",
  searchPath = "pg_catalog,public",
): PrismaClient {
  const url = new URL(databaseUrl);
  url.username = loginRole;
  url.password = "";
  url.searchParams.set(
    "options",
    `-c search_path=${searchPath} -c lock_timeout=2s -c statement_timeout=30s`,
  );
  return new PrismaClient({
    adapter: new PrismaPg({
      connectionString: url.toString(),
      connectionTimeoutMillis: 10_000,
    }),
  });
}

async function expectRuntimeAccepted(): Promise<void> {
  const pairs = [
    ["meddoc_runtime", "quillmd_runtime"],
    ["meddoc_release_control", "quillmd_release_control"],
    ["meddoc_release_security", "quillmd_release_security"],
    ["meddoc_audit_dispatcher", "quillmd_audit_dispatcher"],
    ["meddoc_auth_email_dispatcher", "quillmd_auth_email_dispatcher"],
    ["meddoc_backup", "quillmd_backup"],
  ] as const;
  for (const [loginRole, boundaryRole] of pairs) {
    await expectProfileAccepted(loginRole, boundaryRole);
  }
}

async function expectProfileAccepted(
  loginRole: string,
  boundaryRole: string,
): Promise<void> {
  diagnosticStage = `${diagnosticContext}:runtime-accepted:${loginRole}`;
  const prisma = principalClient(loginRole);
  try {
    const startedAt = performance.now();
    await assertExactDatabasePrincipal({ prisma, loginRole, boundaryRole });
    assert(
      performance.now() - startedAt < 30_000,
      `${loginRole} catalog proof must remain inside its 30s timeout budget`,
    );
  } finally {
    await prisma.$disconnect();
  }
}

async function expectRuntimeRejected(
  label: string,
  searchPath = "pg_catalog,public",
): Promise<void> {
  diagnosticStage = `${diagnosticContext}:runtime-rejected:${label}`;
  const prisma = principalClient("meddoc_runtime", searchPath);
  let rejected = false;
  try {
    await assertExactDatabasePrincipal({
      prisma,
      loginRole: "meddoc_runtime",
      boundaryRole: "quillmd_runtime",
    });
  } catch {
    rejected = true;
  } finally {
    await prisma.$disconnect();
  }
  assert(rejected, `${label} must reject runtime startup`);
}

async function expectMigrationRejected(
  admin: Client,
  label: string,
): Promise<void> {
  diagnosticStage = `${diagnosticContext}:migration-rejected:${label}`;
  let rejected = false;
  try {
    await admin.query(migrationSql);
  } catch {
    rejected = true;
    await admin.query("ROLLBACK");
  }
  assert(rejected, `${label} must reject v9`);
}

async function withCatalogDrift(input: {
  admin: Client;
  label: string;
  install: string;
  remove: string;
  reconcile?: string;
}): Promise<void> {
  diagnosticContext = input.label;
  diagnosticStage = `install-drift:${input.label}`;
  await input.admin.query(input.install);
  try {
    await expectRuntimeRejected(input.label);
  } finally {
    diagnosticStage = `remove-drift:${input.label}`;
    await input.admin.query(input.remove);
    if (input.reconcile) {
      diagnosticStage = `reconcile-drift:${input.label}`;
      await input.admin.query(input.reconcile);
    }
  }
  await expectProfileAccepted("meddoc_runtime", "quillmd_runtime");
}

async function main(): Promise<void> {
  const admin = new Client({ connectionString: databaseUrl });
  await admin.connect();
  try {
    const version = await admin.query<{ major: number }>(
      `SELECT current_setting('server_version_num')::INTEGER / 10000 AS major`,
    );
    assert.equal(version.rows[0]?.major, 16);

    const pristine = await admin.query<{ helper_absent: boolean }>(
      `SELECT pg_catalog.to_regprocedure(
        'public.quillmd_boundary_password_is_null(text)'
      ) IS NULL AS helper_absent`,
    );
    assert.equal(pristine.rows[0]?.helper_absent, true);

    await admin.query("ALTER ROLE meddoc_runtime CONNECTION LIMIT 2");
    try {
      await expectMigrationRejected(admin, "login attribute drift");
    } finally {
      await admin.query("ALTER ROLE meddoc_runtime CONNECTION LIMIT -1");
    }

    await admin.query(`ALTER ROLE quillmd_runtime
      PASSWORD 'synthetic_exact_principal_boundary_only_20260720'`);
    try {
      await expectMigrationRejected(admin, "NOLOGIN boundary password");
    } finally {
      await admin.query("ALTER ROLE quillmd_runtime PASSWORD NULL");
    }

    await admin.query(`
      CREATE ROLE exact_principal_pre_v9_extra NOLOGIN;
      GRANT exact_principal_pre_v9_extra TO meddoc_runtime
        WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;`);
    try {
      await expectMigrationRejected(admin, "role graph drift");
    } finally {
      await admin.query(`
        REVOKE exact_principal_pre_v9_extra FROM meddoc_runtime;
        DROP ROLE exact_principal_pre_v9_extra;`);
    }

    await admin.query(`
      CREATE ROLE exact_principal_pre_v9_read_closure_extra NOLOGIN;
      GRANT exact_principal_pre_v9_read_closure_extra TO pg_read_all_data
        WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;`);
    try {
      await expectMigrationRejected(admin, "predefined read-role closure drift");
    } finally {
      await admin.query(`
        REVOKE exact_principal_pre_v9_read_closure_extra
          FROM pg_read_all_data;
        DROP ROLE exact_principal_pre_v9_read_closure_extra;`);
    }

    await admin.query(migrationSql);
    // This external runtime-protocol assertion must remain immediately after
    // v9; embedding its deparse manifest under migration SQL is not stable.
    await expectRuntimeAccepted();
    await expectMigrationRejected(admin, "non-pristine v9 rerun");

    await expectRuntimeRejected(
      "unsafe original search_path",
      "public,pg_catalog",
    );

    await withCatalogDrift({
      admin,
      label: "predefined read-role outgoing membership",
      install: `
        CREATE ROLE exact_principal_read_closure_extra NOLOGIN;
        GRANT exact_principal_read_closure_extra TO pg_read_all_data
          WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;`,
      remove: `
        REVOKE exact_principal_read_closure_extra FROM pg_read_all_data;
        DROP ROLE exact_principal_read_closure_extra;`,
    });

    await withCatalogDrift({
      admin,
      label: "login verifier downgrade",
      install: `ALTER ROLE meddoc_runtime
        PASSWORD 'md500000000000000000000000000000000'`,
      remove: `ALTER ROLE meddoc_runtime
        PASSWORD 'synthetic_exact_principal_restored_20260720'`,
    });

    await withCatalogDrift({
      admin,
      label: "system-schema PUBLIC ACL drift",
      install: "GRANT SELECT ON TABLE pg_catalog.pg_authid TO PUBLIC",
      remove: "REVOKE SELECT ON TABLE pg_catalog.pg_authid FROM PUBLIC",
    });

    await withCatalogDrift({
      admin,
      label: "application enum label drift",
      install: `ALTER TYPE public."AllergySeverity"
        RENAME VALUE 'MILD' TO 'MILD_EXACT_PRINCIPAL_DRIFT'`,
      remove: `ALTER TYPE public."AllergySeverity"
        RENAME VALUE 'MILD_EXACT_PRINCIPAL_DRIFT' TO 'MILD'`,
    });

    await withCatalogDrift({
      admin,
      label: "application non-view rule drift",
      install: `CREATE RULE exact_principal_rule_drift
        AS ON UPDATE TO public.patients DO ALSO NOTHING`,
      remove: `DROP RULE exact_principal_rule_drift ON public.patients`,
      reconcile: "VACUUM public.patients",
    });

    await withCatalogDrift({
      admin,
      label: "unapproved login direct application ACL",
      install: `
        CREATE ROLE exact_principal_unapproved_login LOGIN;
        GRANT SELECT ON TABLE public.patients
          TO exact_principal_unapproved_login;`,
      remove: `
        REVOKE SELECT ON TABLE public.patients
          FROM exact_principal_unapproved_login;
        DROP ROLE exact_principal_unapproved_login;`,
    });

    await withCatalogDrift({
      admin,
      label: "NOLOGIN boundary password verifier",
      install: `ALTER ROLE quillmd_runtime
        PASSWORD 'synthetic_exact_principal_boundary_only_20260720'`,
      remove: "ALTER ROLE quillmd_runtime PASSWORD NULL",
    });

    await withCatalogDrift({
      admin,
      label: "template0 latent PUBLIC CONNECT",
      install: "GRANT CONNECT ON DATABASE template0 TO PUBLIC",
      remove: "REVOKE CONNECT ON DATABASE template0 FROM PUBLIC",
    });

    await withCatalogDrift({
      admin,
      label: "database-wide role setting",
      install: `ALTER ROLE ALL IN DATABASE ${quotedDatabase}
        SET statement_timeout TO '31s'`,
      remove: `ALTER ROLE ALL IN DATABASE ${quotedDatabase}
        RESET statement_timeout`,
    });

    await withCatalogDrift({
      admin,
      label: "PUBLIC large-object mutator",
      install: "GRANT EXECUTE ON FUNCTION pg_catalog.lo_unlink(oid) TO PUBLIC",
      remove:
        "REVOKE EXECUTE ON FUNCTION pg_catalog.lo_unlink(oid) FROM PUBLIC",
    });

    await withCatalogDrift({
      admin,
      label: "non-superuser database ACL grantor",
      install: `
        CREATE ROLE exact_principal_acl_grantor NOLOGIN;
        GRANT CONNECT ON DATABASE ${quotedDatabase}
          TO exact_principal_acl_grantor WITH GRANT OPTION;
        SET ROLE exact_principal_acl_grantor;
        GRANT CONNECT ON DATABASE ${quotedDatabase} TO quillmd_runtime;
        RESET ROLE;`,
      remove: `
        SET ROLE exact_principal_acl_grantor;
        REVOKE CONNECT ON DATABASE ${quotedDatabase} FROM quillmd_runtime;
        RESET ROLE;
        REVOKE CONNECT ON DATABASE ${quotedDatabase}
          FROM exact_principal_acl_grantor;
        DROP ROLE exact_principal_acl_grantor;`,
    });

    await withCatalogDrift({
      admin,
      label: "trusted boundary as membership grantor",
      install: `
        CREATE ROLE exact_principal_graph_granted NOLOGIN;
        CREATE ROLE exact_principal_graph_member NOLOGIN;
        GRANT exact_principal_graph_granted TO quillmd_runtime
          WITH ADMIN TRUE, INHERIT TRUE, SET FALSE;
        SET ROLE quillmd_runtime;
        GRANT exact_principal_graph_granted TO exact_principal_graph_member
          WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;
        RESET ROLE;`,
      remove: `
        SET ROLE quillmd_runtime;
        REVOKE exact_principal_graph_granted
          FROM exact_principal_graph_member;
        RESET ROLE;
        REVOKE exact_principal_graph_granted FROM quillmd_runtime;
        DROP ROLE exact_principal_graph_member;
        DROP ROLE exact_principal_graph_granted;`,
    });

    diagnosticContext = "final-baseline";
    await expectRuntimeAccepted();

    process.stdout.write("EXACT_DATABASE_PRINCIPAL_PG_TEST_PASS\n");
  } finally {
    await admin.end();
  }
}

void main().catch(() => {
  if (process.env.EXACT_DATABASE_PRINCIPAL_TEST_DEBUG === "true") {
    process.stderr.write(
      `EXACT_DATABASE_PRINCIPAL_DEBUG_STAGE:${diagnosticStage}\n`,
    );
  }
  process.stderr.write("EXACT_DATABASE_PRINCIPAL_PG_TEST_FAIL\n");
  process.exitCode = 1;
});
