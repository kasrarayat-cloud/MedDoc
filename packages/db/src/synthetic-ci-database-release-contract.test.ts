import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const repositoryRoot = resolve(import.meta.dirname, "../../..");
const read = (path: string): string =>
  readFileSync(resolve(repositoryRoot, path), "utf8");

const rootPackage = JSON.parse(read("package.json")) as {
  scripts: Record<string, string>;
};
const databasePackage = JSON.parse(read("packages/db/package.json")) as {
  scripts: Record<string, string>;
};
const provisioner = read(
  "packages/db/scripts/synthetic-ci-database-release.ts",
);
const testWorkflow = read(".github/workflows/test.yml");
const accessibilityWorkflow = read(".github/workflows/a11y.yml");

describe("closed synthetic CI database release path", () => {
  it("removes supported raw deployment aliases", () => {
    expect(rootPackage.scripts["db:migrate:deploy"]).toBeUndefined();
    expect(databasePackage.scripts["migrate:deploy"]).toBeUndefined();
    expect(rootPackage.scripts["db:migrate:status"]).toContain(
      "database-release:migrate",
    );
    expect(rootPackage.scripts["db:migrate:status"]).toContain(
      "--phase status",
    );
    expect(rootPackage.scripts["db:migrate:synthetic-ci"]).toContain(
      "database-release:synthetic-ci",
    );
    expect(databasePackage.scripts["database-release:synthetic-ci"]).toBe(
      "tsx scripts/synthetic-ci-database-release.ts",
    );
    expect(
      databasePackage.scripts["database-release:synthetic-ci:typecheck"],
    ).toBe("tsc -p tsconfig.synthetic-ci-release.json");
    for (const workflow of [testWorkflow, accessibilityWorkflow]) {
      const typecheck = workflow.indexOf(
        "npm run database-release:synthetic-ci:typecheck -w @meddoc/db",
      );
      const provision = workflow.indexOf(
        "npm run db:migrate:synthetic-ci -- --phase provision",
      );
      expect(typecheck).toBeGreaterThan(-1);
      expect(provision).toBeGreaterThan(typecheck);
    }
  });

  it("keeps the helper synthetic-only by construction", () => {
    expect(provisioner).toContain('const syntheticDatabase = "meddoc_ci_test"');
    expect(provisioner).toContain('const databaseOwner = "meddoc"');
    expect(provisioner).toContain(
      'const requiredAcknowledgement = "isolated-disposable-v1"',
    );
    expect(provisioner).toContain('process.env.GITHUB_ACTIONS !== "true"');
    expect(provisioner).toContain('process.env.CI !== "true"');
    expect(provisioner).toContain(
      'dockerEndpoint !== "unix:///var/run/docker.sock"',
    );
    expect(provisioner).toContain('"_runner_file_commands"');
    expect(provisioner).toContain('"set_env_"');
    expect(provisioner).toContain(
      "SYNTHETIC_CI_DATABASE_RELEASE_GITHUB_ENV_INVALID",
    );
    expect(provisioner).toContain(
      "SYNTHETIC_CI_DATABASE_RELEASE_AMBIENT_ROUTE_REFUSED",
    );
    for (const forbidden of [
      "DATABASE_RELEASE_MIGRATION_ALLOW_PRODUCTION",
      "TEMPLATE_TWIN_LINEAGE_ALLOW_PRODUCTION",
      "AUTH_TOKEN_LINEARIZATION_ALLOW_PRODUCTION",
      "DOCKER_HOST",
      "DOCKER_CONTEXT",
      "QUILLMD_POSTGRES_IMAGE",
    ]) {
      expect(provisioner).toContain(`"${forbidden}"`);
    }
    expect(provisioner).not.toMatch(/process\.argv.*(?:target|database-url)/iu);
    expect(provisioner).not.toContain("prisma migrate deploy");
  });

  it("registers generated raw credentials before any file or child use", () => {
    expect(provisioner).toContain(
      "registerGithubSecretMasks(values, writeCommand)",
    );
    expect(provisioner).toContain("writeSync(1, command)");
    expect(provisioner).toContain("Buffer.byteLength(command)");
    const generation = provisioner.indexOf(
      "const secrets = generateMaskedSyntheticDatabaseSecrets();",
    );
    const firstFileUse = provisioner.indexOf(
      "writeFileSync(backupPath, secrets.backup",
    );
    const firstChildUse = provisioner.indexOf(
      "POSTGRES_PASSWORD: secrets.owner",
    );
    const environmentPublish = provisioner.indexOf(
      "appendGithubEnvironment(\n      boundary.githubEnvironment",
    );

    expect(generation).toBeGreaterThan(-1);
    expect(firstFileUse).toBeGreaterThan(generation);
    expect(firstChildUse).toBeGreaterThan(generation);
    expect(environmentPublish).toBeGreaterThan(generation);
  });

  it("creates only immutable labelled resources with validated cleanup", () => {
    expect(provisioner).toContain('"infra/postgres/Dockerfile"');
    expect(provisioner).toContain('state.imageTag,\n        "infra/postgres"');
    expect(provisioner).toContain('"--read-only"');
    expect(provisioner).toContain('"--user",\n        "999:999"');
    expect(provisioner).toContain('"--cap-drop",\n        "ALL"');
    expect(provisioner).toContain('"--memory",\n        "512m"');
    expect(provisioner).toContain(
      '"/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777"',
    );
    expect(provisioner).toContain(
      '"/var/run/postgresql:rw,noexec,nosuid,nodev,size=16m,uid=999,gid=999,mode=3777"',
    );
    expect(provisioner).toContain(
      'const resourceLabel = "com.quillmd.synthetic-ci-release"',
    );
    expect(provisioner).toContain(
      "SYNTHETIC_CI_DATABASE_RELEASE_RESOURCE_IDENTITY_MISMATCH",
    );
    expect(provisioner).toContain(
      "state.containerName !== `${containerPrefix}${state.token}`",
    );
    expect(provisioner).toContain(
      "state.volumeName !== `${volumePrefix}${state.token}`",
    );
    expect(provisioner).toContain(
      "state.imageTag !== `${imagePrefix}${state.token}`",
    );
    expect(provisioner).toContain(
      '"node:22-bookworm@sha256:175215a1f306ed5df592434b99cc2019f70624373fe49cb659240a618a846aed"',
    );
    expect(provisioner).toContain("`container:${state.containerName}`");
    expect(provisioner).toContain('"no-new-privileges"');
    expect(provisioner).toContain(
      "const executorName = `${state.containerName}-executor`",
    );
    expect(provisioner).toContain(
      '["container", "rm", "--force", executorName]',
    );
    expect(provisioner).not.toContain("nsenter");
    expect(provisioner).not.toContain("sudo");
    expect(provisioner).not.toContain("npmExecPath");
    expect(provisioner).toContain(
      "SYNTHETIC_CI_DATABASE_RELEASE_CHILD_${safeChildCode}",
    );
  });

  it("runs the complete witnessed segmented sequence and exact prerequisites", () => {
    for (const phase of ["lineage-expand", "auth-expand", "pre-v9", "v9"]) {
      expect(provisioner).toContain(`"${phase}"`);
    }
    for (const phase of [
      "guard-index",
      "backfill",
      "indexes",
      "validate",
      "contract",
    ]) {
      expect(provisioner).toContain(`"${phase}"`);
    }
    expect(provisioner).toContain(
      "DATABASE_RELEASE_MIGRATION_APPROVED_TARGET_FINGERPRINT",
    );
    expect(provisioner).toContain(
      "TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT",
    );
    expect(provisioner).toContain(
      "AUTH_TOKEN_LINEARIZATION_APPROVED_TARGET_FINGERPRINT",
    );
    expect(provisioner).toContain("applyLineageProtocol(state, ownerUrl)");
    expect(provisioner).toContain("applyAuthProtocol(state, ownerUrl)");
    expect(provisioner).toContain("provisionReleaseSecurity(state");
    expect(provisioner).toContain("proveExactPrincipals(state, secrets)");
    expect(provisioner).toContain("init-template-twin-roles.sh");
    expect(provisioner).toContain(
      "provision-template-twin-release-security.sh",
    );
    expect(provisioner).toContain(
      "packages/db/scripts/exact-database-principal-preflight.ts",
    );
    expect(provisioner).toContain('"owner.pgpass"');
    expect(provisioner).toContain("`PGPASSFILE=${passwordFile}`");
    expect(provisioner).toContain(
      "PSQL_BIN=psql --no-password --host 127.0.0.1",
    );
    for (const profile of [
      "runtime",
      "release-control",
      "release-security",
      "audit-dispatcher",
      "auth-email-dispatcher",
      "backup",
    ]) {
      expect(provisioner).toContain(`"${profile}"`);
    }
    expect(provisioner).toContain(
      "for (let attempt = 0; attempt < 2; attempt += 1)",
    );
    expect(
      provisioner.match(/authCommand\(state, ownerUrl, "all", fingerprint\)/gu),
    ).toHaveLength(1);
  });

  it.each([
    ["test", testWorkflow],
    ["accessibility", accessibilityWorkflow],
  ])(
    "routes the %s workflow through the shared closed helper",
    (_name, workflow) => {
      expect(workflow).toContain(
        "npm run db:migrate:synthetic-ci -- --phase provision",
      );
      expect(workflow).toContain(
        "npm run db:migrate:synthetic-ci -- --phase cleanup",
      );
      expect(workflow).toContain(
        "QUILLMD_SYNTHETIC_CI_DATABASE_RELEASE: isolated-disposable-v1",
      );
      expect(workflow).toMatch(
        /Destroy isolated synthetic database[\s\S]{0,160}if: always\(\)/u,
      );
      expect(workflow).not.toContain(
        "env.QUILLMD_SYNTHETIC_CI_DATABASE_PROVISIONED == 'true'",
      );
      expect(workflow).not.toContain("db:migrate:deploy");
      expect(workflow).not.toContain("prisma migrate deploy");
      expect(workflow).not.toMatch(/^\s{6}postgres:\s*$/mu);
      expect(workflow).not.toMatch(/^\s+DATABASE_URL:\s+postgresql:\/\//mu);
    },
  );
});
