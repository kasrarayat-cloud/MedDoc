import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const repositoryRoot = resolve(process.cwd(), "../..");
const readRepositoryFile = (path: string): string =>
  readFileSync(resolve(repositoryRoot, path), "utf8");

const compose = readRepositoryFile("docker-compose.yml");
const environmentExample = readRepositoryFile(".env.production.example");
const roleBootstrap = readRepositoryFile(
  "infra/postgres/init-template-twin-roles.sh",
);
const runbook = readRepositoryFile("docs/runbooks/auth-email-dispatcher.md");
const rootPackage = JSON.parse(readRepositoryFile("package.json")) as {
  scripts: Record<string, string>;
};
const appPackage = JSON.parse(
  readRepositoryFile("apps/transcribe-md/package.json"),
) as { scripts: Record<string, string> };

const dispatcherBlock = compose.slice(
  compose.indexOf("  auth-email-dispatcher:"),
  compose.indexOf(
    "  # ── TranscribeMD Solo App",
    compose.indexOf("  auth-email-dispatcher:"),
  ),
);
const postgresBlock = compose.slice(
  compose.indexOf("  postgres:"),
  compose.indexOf("  # ── Next.js App"),
);

describe("authentication email dispatcher deployability contract", () => {
  it("uses an isolated, unexposed, fail-closed service process", () => {
    expect(dispatcherBlock).toContain("env_file: []");
    expect(dispatcherBlock).toContain("read_only: true");
    expect(dispatcherBlock).toContain("no-new-privileges:true");
    expect(dispatcherBlock).toContain("cap_drop:\n      - ALL");
    expect(dispatcherBlock).not.toMatch(/^\s+ports:/mu);
    expect(dispatcherBlock).toContain(
      "DATABASE_URL: postgresql://meddoc_auth_email_dispatcher:",
    );
    expect(dispatcherBlock).toContain(
      "QUILLMD_SERVICE_ROLE: auth-email-dispatcher",
    );
    expect(dispatcherBlock).toContain(
      "NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL: ${TRANSCRIBE_MD_AUTH_URL:-https://app.quillmd.com}",
    );
    expect(dispatcherBlock).toContain(
      "RESEND_FROM_VERIFIED: ${RESEND_FROM_VERIFIED:-false}",
    );
    expect(dispatcherBlock).toContain("auth_email_database: {}");
    expect(dispatcherBlock).toContain("auth_email_egress:");
    expect(dispatcherBlock).toContain("gw_priority: 1");
    expect(dispatcherBlock).not.toMatch(/^\s+- default$/gmu);
    expect(postgresBlock).toContain("- auth_email_database");
    expect(compose).toContain("auth_email_database:\n    internal: true");
    for (const credential of [
      "DB_PASSWORD",
      "DB_RUNTIME_PASSWORD",
      "DB_RELEASE_CONTROL_PASSWORD",
      "DB_RELEASE_SECURITY_PASSWORD",
      "DB_AUDIT_DISPATCHER_PASSWORD",
      "DB_AUTH_EMAIL_DISPATCHER_PASSWORD",
      "AUTH_SECRET",
      "ANTHROPIC_API_KEY",
      "OPENAI_API_KEY",
      "DEEPGRAM_API_KEY",
      "MINIO_ACCESS_KEY",
      "MINIO_SECRET_KEY",
      "REDIS_URL",
    ]) {
      expect(dispatcherBlock).toContain(`${credential}: ""`);
    }
  });

  it("requires production database and object-store credentials", () => {
    for (const credential of [
      "DB_PASSWORD",
      "DB_RUNTIME_PASSWORD",
      "DB_RELEASE_CONTROL_PASSWORD",
      "DB_AUDIT_DISPATCHER_PASSWORD",
      "DB_AUTH_EMAIL_DISPATCHER_PASSWORD",
      "MINIO_ROOT_PASSWORD",
      "MINIO_KMS_SECRET_KEY",
    ]) {
      expect(compose).toContain(`\${${credential}:?${credential} is required}`);
    }
    expect(compose).not.toMatch(/changeme(?:_|\b)/u);
    expect(compose).not.toMatch(/\$\{DB_[A-Z_]+:-/u);
  });

  it("binds liveness to the bounded dispatcher progress heartbeat", () => {
    expect(dispatcherBlock).toContain("/tmp/auth-email-dispatcher-heartbeat");
    expect(dispatcherBlock).toContain("-lt 90");
    expect(dispatcherBlock).toContain("start_period: 60s");
    expect(dispatcherBlock).toContain("stop_grace_period: 45s");
  });

  it("provisions an exact dedicated login and boundary role", () => {
    expect(environmentExample).toContain(
      "DB_AUTH_EMAIL_DISPATCHER_PASSWORD=CHANGE_ME_DISTINCT_AUTH_EMAIL_DISPATCHER_DB_PASSWORD",
    );
    expect(roleBootstrap).toContain(
      "DB_AUTH_EMAIL_DISPATCHER_PASSWORD is required",
    );
    expect(roleBootstrap).toContain(
      "CREATE ROLE quillmd_auth_email_dispatcher NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS",
    );
    expect(roleBootstrap).toContain(
      "CREATE ROLE meddoc_auth_email_dispatcher LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOREPLICATION NOBYPASSRLS",
    );
    expect(roleBootstrap).toContain(
      "GRANT quillmd_auth_email_dispatcher TO meddoc_auth_email_dispatcher",
    );
    expect(roleBootstrap).toContain("membership.admin_option");
    expect(
      compose.match(/^\s+DB_AUTH_EMAIL_DISPATCHER_PASSWORD: ""$/gmu),
    ).toHaveLength(7);
  });

  it("ships repeatable operator entrypoints and a fail-closed runbook", () => {
    expect(appPackage.scripts["auth-email-dispatcher"]).toBe(
      "tsx src/auth-email-dispatcher.ts",
    );
    expect(rootPackage.scripts["auth-email-dispatcher"]).toBe(
      "npm run auth-email-dispatcher -w transcribe-md",
    );
    expect(runbook).toContain(
      "production authority and provider approval pending",
    );
    expect(runbook).toContain("docker compose stop auth-email-dispatcher");
    expect(runbook).toContain("Never use a physician or patient identity");
    expect(runbook).toContain("Do not delete outbox rows or tokens");
  });
});
