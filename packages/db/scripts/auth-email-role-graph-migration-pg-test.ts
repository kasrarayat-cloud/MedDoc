#!/usr/bin/env tsx

// Actual-PostgreSQL negative proof for the v6 data-bearing role-graph guard.
// Both targets must be disposable databases migrated through v5 only. Cluster
// role mutations are limited to fixed synthetic/exact roles and are removed.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { Client } from "pg";
import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";

import { assertNonProdDatabase } from "../src/db-guard";

const absentUrl =
  process.env.AUTH_EMAIL_ROLE_GRAPH_ABSENT_TEST_DATABASE_URL?.trim();
const presentUrl =
  process.env.AUTH_EMAIL_ROLE_GRAPH_PRESENT_TEST_DATABASE_URL?.trim();
if (!absentUrl || !presentUrl || absentUrl === presentUrl) {
  throw new Error("Two distinct disposable pre-v6 database URLs are required");
}
const absentTarget = assertNonProdDatabase(absentUrl);
const presentTarget = assertNonProdDatabase(presentUrl);
for (const target of [absentTarget, presentTarget]) {
  if (
    !/^meddoc_auth_role_v6_(?:absent|present)_test_[a-z0-9_]+$/u.test(
      target.database,
    )
  ) {
    throw new Error(
      "Exact disposable auth role-graph database names are required",
    );
  }
}
if (
  process.env.AUTH_EMAIL_ROLE_GRAPH_TEST_CLUSTER_ACK !==
  `${absentTarget.database}:${presentTarget.database}`
) {
  throw new Error("Exact disposable cluster-role acknowledgement is required");
}

const migrationSql = readFileSync(
  fileURLToPath(
    new URL(
      "../prisma/migrations/20260720170000_auth_email_outbox_and_dispatcher_v6/migration.sql",
      import.meta.url,
    ),
  ),
  "utf8",
);
const probeRole = `synthetic_auth_role_graph_${process.pid}`;
assert.match(probeRole, /^[a-z0-9_]+$/u);

async function connect(url: string): Promise<Client> {
  const client = new Client({ connectionString: url });
  await client.connect();
  return client;
}

async function assertPreV6(client: Client): Promise<void> {
  const result = await client.query<{ exists: boolean }>(
    `SELECT to_regclass('public.auth_email_outbox') IS NOT NULL AS "exists"`,
  );
  assert.equal(
    result.rows[0]?.exists,
    false,
    "target must be migrated only through v5",
  );
}

async function expectMigrationRejected(
  client: Client,
  label: string,
): Promise<void> {
  let rejected = false;
  try {
    await client.query(migrationSql);
  } catch {
    rejected = true;
    // The migration owns an explicit transaction. A deliberately triggered
    // guard failure leaves this session in an aborted transaction until the
    // harness rolls it back; without this, subsequent negative cases do not
    // test the graph at all and cleanup cannot remove the synthetic roles.
    await client.query("ROLLBACK");
  }
  assert(rejected, `${label} must reject v6`);
  await assertPreV6(client);
}

async function grant(
  client: Client,
  granted: string,
  member: string,
  setOption = false,
): Promise<void> {
  await client.query(
    `GRANT "${granted}" TO "${member}"
     WITH ADMIN FALSE, INHERIT TRUE, SET ${setOption ? "TRUE" : "FALSE"}`,
  );
}

async function revoke(
  client: Client,
  granted: string,
  member: string,
): Promise<void> {
  await client.query(`REVOKE "${granted}" FROM "${member}"`);
}

function principalClient(
  baseUrl: string,
  role: string,
  assumedRole?: string,
): PrismaClient {
  const url = new URL(baseUrl);
  url.username = role;
  url.password = "";
  const options = ["-c search_path=pg_catalog,public"];
  if (assumedRole) {
    url.username = new URL(baseUrl).username;
    options.push(`-c role=${assumedRole}`);
  }
  const existing = url.searchParams.get("options")?.trim() ?? "";
  url.searchParams.set(
    "options",
    [existing, ...options].filter(Boolean).join(" "),
  );
  return new PrismaClient({
    adapter: new PrismaPg({ connectionString: url.toString() }),
  });
}

interface V6DispatcherPrincipalRow {
  sessionRole: string;
  currentRole: string;
  loginCanLogin: boolean;
  loginSuperuser: boolean;
  loginCreateDb: boolean;
  loginCreateRole: boolean;
  loginInherits: boolean;
  loginReplication: boolean;
  loginBypassRls: boolean;
  loginConnectionLimit: number;
  loginValidUntil: Date | null;
  loginMemberships: string[];
  loginMembers: string[];
  loginHasInvalidMembership: boolean;
  boundaryCanLogin: boolean;
  boundarySuperuser: boolean;
  boundaryCreateDb: boolean;
  boundaryCreateRole: boolean;
  boundaryInherits: boolean;
  boundaryReplication: boolean;
  boundaryBypassRls: boolean;
  boundaryConnectionLimit: number;
  boundaryValidUntil: Date | null;
  boundaryMemberships: string[];
  boundaryMembers: string[];
  boundaryHasInvalidMember: boolean;
}

/**
 * The v6 migration owns only the dispatcher role graph. The final runtime
 * attestor also verifies the complete v9 ACL/catalog manifest and therefore
 * must not be invoked against an authentic pre-v9 database. Keep this proof
 * scoped to the exact v6 login, boundary, membership-option, grantor, and
 * session-user contract; the v9 PostgreSQL harness owns final startup proof.
 */
async function assertV6DispatcherSessionRoleGraph(input: {
  prisma: PrismaClient;
  loginRole: string;
  boundaryRole: string;
}): Promise<void> {
  const rows = await input.prisma.$queryRaw<V6DispatcherPrincipalRow[]>`
    SELECT session_user::text AS "sessionRole",
      current_user::text AS "currentRole",
      login.rolcanlogin AS "loginCanLogin",
      login.rolsuper AS "loginSuperuser",
      login.rolcreatedb AS "loginCreateDb",
      login.rolcreaterole AS "loginCreateRole",
      login.rolinherit AS "loginInherits",
      login.rolreplication AS "loginReplication",
      login.rolbypassrls AS "loginBypassRls",
      login.rolconnlimit AS "loginConnectionLimit",
      login.rolvaliduntil AS "loginValidUntil",
      ARRAY(
        SELECT granted.rolname::text
        FROM pg_catalog.pg_auth_members membership
        JOIN pg_catalog.pg_roles granted
          ON granted.oid = membership.roleid
        WHERE membership.member = login.oid
        ORDER BY granted.rolname COLLATE "C"
      ) AS "loginMemberships",
      ARRAY(
        SELECT member_role.rolname::text
        FROM pg_catalog.pg_auth_members membership
        JOIN pg_catalog.pg_roles member_role
          ON member_role.oid = membership.member
        WHERE membership.roleid = login.oid
        ORDER BY member_role.rolname COLLATE "C"
      ) AS "loginMembers",
      EXISTS (
        SELECT 1
        FROM pg_catalog.pg_auth_members membership
        JOIN pg_catalog.pg_roles grantor
          ON grantor.oid = membership.grantor
        WHERE membership.member = login.oid
          AND (
            membership.admin_option
            OR membership.inherit_option IS DISTINCT FROM TRUE
            OR membership.set_option IS DISTINCT FROM FALSE
            OR grantor.rolsuper IS DISTINCT FROM TRUE
          )
      ) AS "loginHasInvalidMembership",
      boundary.rolcanlogin AS "boundaryCanLogin",
      boundary.rolsuper AS "boundarySuperuser",
      boundary.rolcreatedb AS "boundaryCreateDb",
      boundary.rolcreaterole AS "boundaryCreateRole",
      boundary.rolinherit AS "boundaryInherits",
      boundary.rolreplication AS "boundaryReplication",
      boundary.rolbypassrls AS "boundaryBypassRls",
      boundary.rolconnlimit AS "boundaryConnectionLimit",
      boundary.rolvaliduntil AS "boundaryValidUntil",
      ARRAY(
        SELECT granted.rolname::text
        FROM pg_catalog.pg_auth_members membership
        JOIN pg_catalog.pg_roles granted
          ON granted.oid = membership.roleid
        WHERE membership.member = boundary.oid
        ORDER BY granted.rolname COLLATE "C"
      ) AS "boundaryMemberships",
      ARRAY(
        SELECT member_role.rolname::text
        FROM pg_catalog.pg_auth_members membership
        JOIN pg_catalog.pg_roles member_role
          ON member_role.oid = membership.member
        WHERE membership.roleid = boundary.oid
        ORDER BY member_role.rolname COLLATE "C"
      ) AS "boundaryMembers",
      EXISTS (
        SELECT 1
        FROM pg_catalog.pg_auth_members membership
        JOIN pg_catalog.pg_roles member_role
          ON member_role.oid = membership.member
        JOIN pg_catalog.pg_roles grantor
          ON grantor.oid = membership.grantor
        WHERE membership.roleid = boundary.oid
          AND (
            member_role.rolname <> ${input.loginRole}
            OR membership.admin_option
            OR membership.inherit_option IS DISTINCT FROM TRUE
            OR membership.set_option IS DISTINCT FROM FALSE
            OR grantor.rolsuper IS DISTINCT FROM TRUE
          )
      ) AS "boundaryHasInvalidMember"
    FROM pg_catalog.pg_roles login
    CROSS JOIN pg_catalog.pg_roles boundary
    WHERE login.rolname = ${input.loginRole}
      AND boundary.rolname = ${input.boundaryRole}
  `;
  const principal = rows[0];
  if (
    rows.length !== 1 ||
    !principal ||
    principal.sessionRole !== input.loginRole ||
    principal.currentRole !== input.loginRole ||
    principal.loginCanLogin !== true ||
    principal.loginSuperuser ||
    principal.loginCreateDb ||
    principal.loginCreateRole ||
    principal.loginInherits !== true ||
    principal.loginReplication ||
    principal.loginBypassRls ||
    principal.loginConnectionLimit !== -1 ||
    principal.loginValidUntil !== null ||
    principal.loginHasInvalidMembership ||
    principal.loginMemberships.length !== 1 ||
    principal.loginMemberships[0] !== input.boundaryRole ||
    principal.loginMembers.length !== 0 ||
    principal.boundaryCanLogin ||
    principal.boundarySuperuser ||
    principal.boundaryCreateDb ||
    principal.boundaryCreateRole ||
    principal.boundaryInherits ||
    principal.boundaryReplication ||
    principal.boundaryBypassRls ||
    principal.boundaryConnectionLimit !== -1 ||
    principal.boundaryValidUntil !== null ||
    principal.boundaryMemberships.length !== 0 ||
    principal.boundaryMembers.length !== 1 ||
    principal.boundaryMembers[0] !== input.loginRole ||
    principal.boundaryHasInvalidMember
  ) {
    throw new Error("Exact v6 dispatcher session role graph is required.");
  }
}

async function expectV6PrincipalRejected(
  operation: () => Promise<void>,
  label: string,
): Promise<void> {
  let rejected = false;
  try {
    await operation();
  } catch {
    rejected = true;
  }
  assert(rejected, `${label} must reject dispatcher startup`);
}

async function main(): Promise<void> {
  const absent = await connect(absentUrl);
  const present = await connect(presentUrl);
  let createdOptionalLogin = false;
  try {
    await assertPreV6(absent);
    await assertPreV6(present);
    const optional = await absent.query<{ exists: boolean }>(
      `SELECT EXISTS (
         SELECT 1 FROM pg_roles WHERE rolname = 'meddoc_release_security'
       ) AS "exists"`,
    );
    assert.equal(
      optional.rows[0]?.exists,
      false,
      "absent lifecycle must start absent",
    );

    await absent.query(`CREATE ROLE "${probeRole}" NOLOGIN`);

    await grant(absent, probeRole, "quillmd_auth_email_dispatcher");
    await expectMigrationRejected(
      absent,
      "auth dispatcher boundary outgoing edge",
    );
    await revoke(absent, probeRole, "quillmd_auth_email_dispatcher");

    await grant(absent, "meddoc_auth_email_dispatcher", probeRole);
    await expectMigrationRejected(absent, "auth dispatcher login inbound edge");
    await revoke(absent, "meddoc_auth_email_dispatcher", probeRole);

    await grant(absent, probeRole, "meddoc_auth_email_dispatcher");
    await expectMigrationRejected(absent, "auth dispatcher login extra edge");
    await revoke(absent, probeRole, "meddoc_auth_email_dispatcher");

    await grant(
      absent,
      "quillmd_auth_email_dispatcher",
      "meddoc_auth_email_dispatcher",
      true,
    );
    await expectMigrationRejected(absent, "auth dispatcher SET ROLE option");
    await grant(
      absent,
      "quillmd_auth_email_dispatcher",
      "meddoc_auth_email_dispatcher",
    );

    await absent.query(migrationSql);
    const absentInstalled = await absent.query<{ exists: boolean }>(
      `SELECT to_regclass('public.auth_email_outbox') IS NOT NULL AS "exists"`,
    );
    assert.equal(absentInstalled.rows[0]?.exists, true);

    await present.query(
      `CREATE ROLE meddoc_release_security LOGIN NOSUPERUSER NOCREATEDB
       NOCREATEROLE INHERIT NOREPLICATION NOBYPASSRLS`,
    );
    createdOptionalLogin = true;
    await grant(present, "quillmd_release_security", "meddoc_release_security");
    await present.query(migrationSql);
    const presentInstalled = await present.query<{ exists: boolean }>(
      `SELECT to_regclass('public.auth_email_outbox') IS NOT NULL AS "exists"`,
    );
    assert.equal(presentInstalled.rows[0]?.exists, true);

    const auditPrincipal = principalClient(
      absentUrl,
      "meddoc_audit_dispatcher",
    );
    const authPrincipal = principalClient(
      absentUrl,
      "meddoc_auth_email_dispatcher",
    );
    const assumedAuthPrincipal = principalClient(
      absentUrl,
      new URL(absentUrl).username,
      "meddoc_auth_email_dispatcher",
    );
    try {
      await assertV6DispatcherSessionRoleGraph({
        prisma: auditPrincipal,
        loginRole: "meddoc_audit_dispatcher",
        boundaryRole: "quillmd_audit_dispatcher",
      });
      await assertV6DispatcherSessionRoleGraph({
        prisma: authPrincipal,
        loginRole: "meddoc_auth_email_dispatcher",
        boundaryRole: "quillmd_auth_email_dispatcher",
      });
      await expectV6PrincipalRejected(
        () =>
          assertV6DispatcherSessionRoleGraph({
            prisma: assumedAuthPrincipal,
            loginRole: "meddoc_auth_email_dispatcher",
            boundaryRole: "quillmd_auth_email_dispatcher",
          }),
        "session-user/current-user mismatch",
      );

      await grant(absent, probeRole, "quillmd_audit_dispatcher");
      await expectV6PrincipalRejected(
        () =>
          assertV6DispatcherSessionRoleGraph({
            prisma: auditPrincipal,
            loginRole: "meddoc_audit_dispatcher",
            boundaryRole: "quillmd_audit_dispatcher",
          }),
        "audit boundary nested membership",
      );
      await revoke(absent, probeRole, "quillmd_audit_dispatcher");

      await grant(absent, probeRole, "quillmd_auth_email_dispatcher");
      await expectV6PrincipalRejected(
        () =>
          assertV6DispatcherSessionRoleGraph({
            prisma: authPrincipal,
            loginRole: "meddoc_auth_email_dispatcher",
            boundaryRole: "quillmd_auth_email_dispatcher",
          }),
        "auth-email boundary nested membership",
      );
      await revoke(absent, probeRole, "quillmd_auth_email_dispatcher");
    } finally {
      await Promise.allSettled([
        auditPrincipal.$disconnect(),
        authPrincipal.$disconnect(),
        assumedAuthPrincipal.$disconnect(),
      ]);
    }

    process.stdout.write(
      `${JSON.stringify({
        profile: "auth-email-v6-exact-role-graph",
        synthetic: true,
        outgoingBoundaryRejected: true,
        inboundLoginRejected: true,
        extraLoginEdgeRejected: true,
        setOptionRejected: true,
        optionalReleaseSecurityAbsentAccepted: true,
        optionalReleaseSecurityPresentAccepted: true,
        cleanGraphsAccepted: true,
        auditDispatcherV6SessionGraphAccepted: true,
        authDispatcherV6SessionGraphAccepted: true,
        nestedDispatcherV6SessionGraphsRejected: true,
        assumedRoleSessionRejected: true,
      })}\n`,
    );
  } finally {
    await absent
      .query(`REVOKE "${probeRole}" FROM quillmd_auth_email_dispatcher`)
      .catch(() => undefined);
    await absent
      .query(`REVOKE meddoc_auth_email_dispatcher FROM "${probeRole}"`)
      .catch(() => undefined);
    await absent
      .query(`REVOKE "${probeRole}" FROM meddoc_auth_email_dispatcher`)
      .catch(() => undefined);
    await absent
      .query(`DROP ROLE IF EXISTS "${probeRole}"`)
      .catch(() => undefined);
    if (createdOptionalLogin) {
      await absent
        .query(`REVOKE quillmd_release_security FROM meddoc_release_security`)
        .catch(() => undefined);
      await absent
        .query(`DROP ROLE IF EXISTS meddoc_release_security`)
        .catch(() => undefined);
    }
    await Promise.allSettled([absent.end(), present.end()]);
  }
}

void main().catch((error: unknown) => {
  void error;
  process.stderr.write("AUTH_EMAIL_ROLE_GRAPH_PG_TEST_FAILED\n");
  process.exitCode = 1;
});
