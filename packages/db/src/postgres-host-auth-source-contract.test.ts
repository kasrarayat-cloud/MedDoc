import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { QUILLMD_POSTGRES_HBA_CONTRACT } from "./postgres-host-auth";

const repositoryRoot = resolve(import.meta.dirname, "../../..");
const source = (path: string) =>
  readFileSync(resolve(repositoryRoot, path), "utf8");
const hba = source("infra/postgres/quillmd-pg_hba.conf");
const verifier = source("infra/postgres/verify-quillmd-host-auth.sh");
const postgresDockerfile = source("infra/postgres/Dockerfile");
const postgresDockerignore = source("infra/postgres/.dockerignore");
const postgresEntrypoint = source(
  "infra/postgres/quillmd-postgres-entrypoint.sh",
);
const productionCompose = source("docker-compose.yml");
const qaCompose = source("docker-compose.qa.yml");
const runtimeGate = source("packages/db/src/production-runtime-principal.ts");
const preflight = source(
  "packages/db/scripts/exact-database-principal-preflight.ts",
);
const pgHarness = source("packages/db/scripts/postgres-host-auth-pg-test.ts");
const humanReleaseWorkflow = source(
  ".github/workflows/template-twin-human-release-gate.yml",
);

describe("PostgreSQL host-authentication source contract", () => {
  it("freezes an enumerated SCRAM-only TCP policy with reject catch-alls", () => {
    const rules = hba
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0 && !line.startsWith("#"));
    expect(rules).toEqual([
      "local replication all reject",
      "host replication all all reject",
      "local all all trust",
      "host all meddoc,meddoc_runtime,meddoc_release_control,meddoc_release_security,meddoc_audit_dispatcher,meddoc_auth_email_dispatcher,meddoc_backup all scram-sha-256",
      "host all all 0.0.0.0/0 reject",
      "host all all ::0/0 reject",
    ]);
    expect(createHash("sha256").update(hba, "utf8").digest("hex")).toBe(
      QUILLMD_POSTGRES_HBA_CONTRACT.sha256,
    );
  });

  it("runs both PostgreSQL services from the embedded read-only policy", () => {
    for (const compose of [productionCompose, qaCompose]) {
      expect(compose).toContain("hba_file=/etc/postgresql/quillmd-pg_hba.conf");
      expect(compose).toContain("password_encryption=scram-sha-256");
      expect(compose).toContain(
        "quillmd.hba_contract_path=/etc/postgresql/quillmd-pg_hba.conf",
      );
      expect(compose).toContain(
        `quillmd.hba_contract_sha256=${QUILLMD_POSTGRES_HBA_CONTRACT.sha256}`,
      );
      expect(compose).not.toContain(
        "./infra/postgres/quillmd-pg_hba.conf:/etc/postgresql/quillmd-pg_hba.conf",
      );
      expect(compose).not.toContain(
        "./infra/postgres/verify-quillmd-host-auth.sh:/opt/quillmd/verify-quillmd-host-auth.sh",
      );
      expect(compose).toContain(
        'test: ["CMD", "/bin/sh", "/opt/quillmd/verify-quillmd-host-auth.sh"]',
      );
      expect(compose).toContain(
        'POSTGRES_INITDB_ARGS: "--auth-host=scram-sha-256 --auth-local=trust"',
      );
      expect(compose).toContain("read_only: true");
      expect(compose).toContain(
        'entrypoint: ["/usr/local/bin/quillmd-postgres-entrypoint.sh"]',
      );
      expect(compose).toContain(
        "/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777",
      );
      expect(compose).toContain(
        "/var/run/postgresql:rw,noexec,nosuid,nodev,size=16m,uid=999,gid=999,mode=3777",
      );
    }
    expect(productionCompose).toContain(
      "image: ${QUILLMD_POSTGRES_IMAGE:?QUILLMD_POSTGRES_IMAGE must be an immutable sha256 digest}",
    );
    expect(qaCompose).toContain("context: ./infra/postgres");
    expect(qaCompose).toContain("dockerfile: Dockerfile");
  });

  it("builds a root-owned embedded contract behind a strict pre-entrypoint guard", () => {
    expect(postgresDockerignore.trim().split("\n")).toEqual([
      "*",
      "!Dockerfile",
      "!quillmd-pg_hba.conf",
      "!quillmd-postgres-entrypoint.sh",
      "!verify-quillmd-host-auth.sh",
    ]);
    expect(postgresDockerfile).toContain(
      "FROM pgvector/pgvector:pg16@sha256:7d400e340efb42f4d8c9c12c6427adb253f726881a9985d2a471bf0eed824dff",
    );
    expect(postgresDockerfile).toContain("COPY quillmd-pg_hba.conf");
    expect(postgresDockerfile).toContain("COPY verify-quillmd-host-auth.sh");
    expect(postgresDockerfile).toContain(
      "chmod 0444 /etc/postgresql/quillmd-pg_hba.conf",
    );
    expect(postgresDockerfile).toContain(
      "chmod 0555 /opt/quillmd/verify-quillmd-host-auth.sh",
    );
    expect(postgresDockerfile).toContain(
      createHash("sha256").update(postgresEntrypoint, "utf8").digest("hex"),
    );
    expect(postgresDockerfile).toContain(
      'ENTRYPOINT ["/usr/local/bin/quillmd-postgres-entrypoint.sh"]',
    );
    expect(postgresEntrypoint).toContain(QUILLMD_POSTGRES_HBA_CONTRACT.sha256);
    expect(postgresEntrypoint).toContain('[ "$#" -eq 9 ] || fail');
    expect(postgresEntrypoint).toContain(
      "exec /usr/local/bin/docker-entrypoint.sh",
    );
    expect(postgresEntrypoint).toContain(
      "QUILLMD_POSTGRES_IMAGE_CONTRACT_FAIL",
    );
    expect(postgresEntrypoint).not.toContain(
      'exec /usr/local/bin/docker-entrypoint.sh "$@"',
    );
  });

  it("makes the local-owner health proof exact and fixed-output", () => {
    expect(verifier).toContain(QUILLMD_POSTGRES_HBA_CONTRACT.sha256);
    expect(verifier).toContain('sha256sum "$contract_path"');
    expect(verifier).toContain("pg_catalog.pg_hba_file_rules");
    expect(verifier).toContain("pg_catalog.jsonb_agg");
    expect(verifier).toContain("pg_catalog.pg_conf_load_time()");
    expect(verifier).toContain("pg_catalog.pg_postmaster_start_time()");
    expect(verifier).toContain("pg_catalog.inet_client_addr() IS NULL");
    expect(verifier).toContain("QUILLMD_POSTGRES_HOST_AUTH_FAIL");
    expect(verifier).not.toContain("set -x");
  });

  it("proves weak startup and reload fail until an exact postmaster restart", () => {
    expect(pgHarness).toContain("POSTGRES_DOCKERFILE");
    expect(pgHarness).toContain("POSTGRES_HOST_AUTH_WEAK_START_ADMITTED");
    expect(pgHarness).toContain("POSTGRES_HOST_AUTH_WEAK_BYTES_START_ADMITTED");
    expect(pgHarness).toContain("POSTGRES_HOST_AUTH_ROOTFS_MUTATION_ADMITTED");
    expect(pgHarness).toContain("com.quillmd.synthetic-test-owner");
    expect(pgHarness).toContain('isOwnedResource("container"');
    expect(pgHarness).toContain('isOwnedResource("volume"');
    expect(pgHarness).toContain('isOwnedResource("image"');
    expect(pgHarness).toContain("pg_catalog.pg_reload_conf()");
    expect(pgHarness).toContain("POSTGRES_HOST_AUTH_RELOAD_ADMITTED");
    expect(pgHarness).toMatch(/"restart",\s+containerName/u);
    expect(pgHarness).toContain("POSTGRES_HOST_AUTH_PG_TEST_PASS");
    expect(humanReleaseWorkflow).toContain(
      "npm run postgres-host-auth:pg-test -w @meddoc/db",
    );
  });

  it("requires the ordinary TCP-session proof before the catalog proof", () => {
    for (const caller of [runtimeGate, preflight]) {
      const hostAuthentication = caller.indexOf(
        "await assertPostgresHostAuthenticationContract({",
      );
      const catalog = caller.indexOf("await assertExactDatabasePrincipal({");
      expect(hostAuthentication).toBeGreaterThan(-1);
      expect(catalog).toBeGreaterThan(hostAuthentication);
    }
  });
});
