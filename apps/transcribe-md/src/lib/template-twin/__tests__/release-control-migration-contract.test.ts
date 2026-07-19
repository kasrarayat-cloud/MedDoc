import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const repositoryRoot = resolve(process.cwd(), "../..");
const migration = readFileSync(
  resolve(
    repositoryRoot,
    "packages/db/prisma/migrations/20260719160000_template_twin_production_control_plane_v1/migration.sql",
  ),
  "utf8",
);
const hardeningMigration = readFileSync(
  resolve(
    repositoryRoot,
    "packages/db/prisma/migrations/20260719163000_template_twin_production_control_plane_hardening_v2/migration.sql",
  ),
  "utf8",
);
const finalHardeningMigration = readFileSync(
  resolve(
    repositoryRoot,
    "packages/db/prisma/migrations/20260719164000_template_twin_production_control_plane_hardening_v3/migration.sql",
  ),
  "utf8",
);
const route = readFileSync(
  resolve(
    repositoryRoot,
    "apps/transcribe-md/src/app/api/admin/template-twin/releases/route.ts",
  ),
  "utf8",
);
const prismaSchema = readFileSync(
  resolve(repositoryRoot, "packages/db/prisma/schema.prisma"),
  "utf8",
);
const compose = readFileSync(
  resolve(repositoryRoot, "docker-compose.yml"),
  "utf8",
);
const caddy = readFileSync(resolve(repositoryRoot, "Caddyfile"), "utf8");
const roleBootstrap = readFileSync(
  resolve(repositoryRoot, "infra/postgres/init-template-twin-roles.sh"),
  "utf8",
);
const releaseSecurityBootstrap = readFileSync(
  resolve(
    repositoryRoot,
    "infra/postgres/provision-template-twin-release-security.sh",
  ),
  "utf8",
);
const adminFreshness = readFileSync(
  resolve(
    repositoryRoot,
    "apps/transcribe-md/src/lib/admin-session-freshness.ts",
  ),
  "utf8",
);
const sharedAuth = readFileSync(
  resolve(repositoryRoot, "packages/auth/src/index.ts"),
  "utf8",
);

describe("Template Twin production control-plane migration contract", () => {
  it("is additive, empty, and leaves both persisted rollout scopes default-off", () => {
    expect(migration).toContain(
      'CREATE TABLE "template_twin_release_candidates"',
    );
    expect(migration).toContain(
      'CREATE TABLE "template_twin_release_authorities"',
    );
    expect(migration).toContain(
      'CREATE TABLE "template_twin_release_checkpoints"',
    );
    expect(migration).toContain(
      'CREATE TABLE "template_twin_release_metric_snapshots"',
    );
    expect(migration).not.toMatch(
      /UPDATE\s+"template_twin_rollout_controls"[\s\S]{0,160}SET[\s\S]{0,80}"enabled"\s*=\s*TRUE/iu,
    );
    expect(migration).not.toMatch(
      /UPDATE\s+"practices"[\s\S]{0,160}"templateTwinEnabled"\s*=\s*TRUE/iu,
    );
    expect(migration).not.toContain(
      'INSERT INTO "template_twin_release_authorities"',
    );
    expect(migration).toContain(
      "requires a disabled, open-fence rollout baseline",
    );
  });

  it("serializes with rollback and binds enablement to a transaction-local exact release capability", () => {
    expect(migration).toContain("pg_advisory_xact_lock(73119, 20260719)");
    expect(migration).toContain("template_twin_issue_release_capability");
    expect(migration).toContain('cap."transactionId" = txid_current()');
    expect(migration).toContain('cap."backendPid" = pg_backend_pid()');
    expect(migration).toContain(
      "production enablement capability is forged or stale",
    );
    expect(migration).toContain(
      "aab_template_twin_global_release_capability_guard",
    );
    expect(migration).toContain(
      "aab_template_twin_practice_release_capability_guard",
    );
    expect(migration).toContain(
      "Template Twin release capability receipts are immutable",
    );
  });

  it("makes identity, approval, metric, checkpoint, and audit evidence immutable", () => {
    expect(migration).toContain("Template Twin release identity is immutable");
    expect(migration).toContain(
      "Template Twin release evidence is append-only",
    );
    expect(migration).toContain(
      "Template Twin release audit identity is immutable",
    );
    expect(migration).toContain(
      "Template Twin release audit receipt is immutable",
    );
    expect(migration).toContain(
      "Template Twin release evidence cannot be truncated",
    );
    expect(migration).toContain("template_twin_release_approvals_are_current");
    expect(migration).toContain(
      "Revoke the active Template Twin release before revoking its human authority",
    );
  });

  it("enforces a complete ordered rail and current human authority at commit", () => {
    for (const stage of [
      "CANARY",
      "PERCENT_10",
      "PERCENT_25",
      "PERCENT_50",
      "PERCENT_100",
    ]) {
      expect(migration).toContain(`'${stage}'`);
    }
    expect(migration).toContain("creator/finalizer cannot approve");
    expect(migration).toContain("current human approvals are incomplete");
    expect(migration).toContain(
      "checkpoint rail is incomplete or out of order",
    );
    expect(migration).toContain(
      "persisted exposure is outside the release checkpoint",
    );
  });

  it("requires signed runtime and monitoring evidence behind split database roles", () => {
    for (const fragment of [
      "Cluster roles are deliberately provisioned out of band",
      "rolcanlogin = FALSE",
      "rolinherit = FALSE",
      "rolbypassrls = FALSE",
      'CREATE TABLE "template_twin_release_attestation_keys"',
      "template_twin_register_runtime_attestation",
      "template_twin_release_runtime_ready",
      "template_twin_issue_metric_receipt",
      "template_twin_verify_release_actor",
      "Template Twin metric insert requires a signed monitoring receipt",
      'REVOKE ALL ON "template_twin_release_attestation_keys"',
    ]) {
      expect(hardeningMigration).toContain(fragment);
    }
    expect(hardeningMigration).toContain(`key."revokedAt" IS NULL`);
    expect(hardeningMigration).toContain(
      `attestation."expiresAt" > clock_timestamp() + INTERVAL '30 seconds'`,
    );
    expect(hardeningMigration).toContain(
      'REVOKE ALL ON "template_twin_release_attestation_keys", "user_sessions"',
    );
    expect(hardeningMigration).toContain(
      "Template Twin database roles or login principals are absent or not least-privilege",
    );
    for (const principal of [
      "meddoc_runtime",
      "meddoc_release_control",
      "meddoc_audit_dispatcher",
      "quillmd_audit_dispatcher",
    ]) {
      expect(hardeningMigration).toContain(principal);
    }
    expect(hardeningMigration).toContain(
      'GRANT SELECT, UPDATE ON "template_twin_audit_outbox"',
    );
    expect(hardeningMigration).toContain(
      'REVOKE UPDATE, DELETE, TRUNCATE ON "template_twin_audit_outbox" FROM quillmd_runtime',
    );
    expect(hardeningMigration).not.toContain("ALTER DEFAULT PRIVILEGES");
    expect(hardeningMigration).not.toContain(
      'GRANT INSERT ON "template_twin_release_capabilities"',
    );
  });

  it("revokes public execution on every sensitive definer and maps raw release objects in Prisma", () => {
    for (const signature of [
      "template_twin_release_approvals_are_current(\n  UUID, CHAR(64)\n) FROM PUBLIC",
      "template_twin_guard_release_approval_insert()\n  FROM PUBLIC",
      "template_twin_assert_release_audit_delivery()\n  FROM PUBLIC",
      "template_twin_check_release_audit_delivery()\n  FROM PUBLIC",
      "template_twin_assert_release_control_coupling()\n  FROM PUBLIC",
    ]) {
      expect(hardeningMigration).toContain(signature);
    }
    for (const mapping of [
      'map: "template_twin_release_runtime_requirement_release_fkey"',
      'map: "template_twin_release_runtime_attestation_release_fkey"',
      'map: "template_twin_release_runtime_attestation_key_fkey"',
      'map: "template_twin_release_metric_receipt_release_fkey"',
      'map: "template_twin_release_metric_receipt_key_fkey"',
      'map: "template_twin_release_capability_release_fkey"',
      "@@ignore",
    ]) {
      expect(prismaSchema).toContain(mapping);
    }
  });

  it("keeps additive default-off migration locking and amortizes deferred coupling scans", () => {
    expect(hardeningMigration).toContain(
      "pg_advisory_xact_lock(73119, 20260719)",
    );
    expect(hardeningMigration).toContain(
      "Template Twin hardening v2 requires an unused, disabled, open-fence control plane",
    );
    expect(hardeningMigration).not.toMatch(
      /UPDATE\s+"template_twin_rollout_controls"[\s\S]{0,160}SET[\s\S]{0,80}"enabled"\s*=\s*TRUE/iu,
    );
    expect(hardeningMigration).toContain(
      "template_twin_mark_release_coupling_dirty",
    );
    expect(hardeningMigration).toContain(
      'CREATE TABLE "template_twin_release_coupling_receipts"',
    );
    expect(hardeningMigration).toContain('"backendPid" = pg_backend_pid()');
    expect(hardeningMigration).toContain(
      '"transactionId" = txid_current()',
    );
    expect(hardeningMigration).not.toContain(
      "meddoc.template_twin_release_coupling_verified_tx",
    );
    expect(hardeningMigration).toContain(
      "AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE",
    );
  });

  it("makes authority loss and tenant deactivation atomic kill-switch events", () => {
    expect(hardeningMigration).toContain(
      "template_twin_revoke_release_authority",
    );
    expect(hardeningMigration).toContain(
      "template_twin_user_lifecycle_authority_revoke",
    );
    expect(hardeningMigration).toContain(
      "aaa_template_twin_practice_deactivation_guard",
    );
    expect(hardeningMigration).toContain(
      'COUNT(DISTINCT latest."actorId") = 4',
    );
    expect(hardeningMigration).toContain(
      "template_twin_one_active_release_authority_per_human_key",
    );
    expect(finalHardeningMigration).toContain(
      'NOT (\'SUPER_ADMIN\'::public."Product" = ANY(NEW."products"))',
    );
    expect(finalHardeningMigration).toContain(
      '"mfaEnabled", "mfaVerifiedAt", "products", "forceLogoutAt"',
    );
  });

  it("freezes exact manifests and enforces monitoring, epoch, and terminal state in PostgreSQL", () => {
    for (const fragment of [
      "template_twin_guard_release_manifest_insert",
      "template_twin_validate_release_freeze_manifest",
      "computed_practice_sha",
      "computed_runtime_sha",
      "template_twin_guard_checkpoint_pass",
      'receipt."releaseGeneration" = metric."releaseGeneration"',
      'receipt."globalGeneration" = metric."globalGeneration"',
      "STABLE_100 requires the exact final checkpoint to pass",
      "critical monitoring evidence requires atomic release revocation and disable",
      "rollout audit evidence cannot pre-seed a future or missing control generation",
      "template_twin_canonical_json",
      "template_twin_guardrail_policy_is_exact",
      'CREATE TABLE "template_twin_release_action_receipts"',
      "template_twin_issue_release_action_receipt",
      "Template Twin checkpoint activation evidence is immutable",
      "Template Twin attestation keys permit only a monotonic current revocation",
    ]) {
      expect(hardeningMigration).toContain(fragment);
    }
  });

  it("puts caller temporary schemas last and keeps raw evidence unreadable to runtime", () => {
    expect(finalHardeningMigration).toContain(
      "SET search_path TO pg_catalog, public, pg_temp",
    );
    expect(finalHardeningMigration).toContain(
      "SET search_path = pg_catalog, public, pg_temp",
    );
    expect(finalHardeningMigration).toContain(
      "procedure.proname LIKE 'template_twin_%'",
    );
    expect(finalHardeningMigration).toContain(
      "ALTER FUNCTION %I.%I(%s) SET search_path TO pg_catalog, public, pg_temp",
    );
    expect(finalHardeningMigration).toContain(
      "@> ARRAY['search_path=pg_catalog, public, pg_temp']::TEXT[]",
    );
    expect(finalHardeningMigration).toContain(
      '"template_twin_release_authorities",',
    );
    expect(finalHardeningMigration).toContain(
      '"template_twin_release_metric_snapshots",',
    );
    expect(finalHardeningMigration).toContain(
      '"template_twin_release_capabilities",',
    );
    expect(finalHardeningMigration).toContain("FROM quillmd_runtime");
    expect(finalHardeningMigration).toContain(
      "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
    );
  });

  it("couples key revocation and verifies control sessions without raw session access", () => {
    expect(finalHardeningMigration).toContain(
      "template_twin_release_attestation_key_coupling_guard",
    );
    expect(finalHardeningMigration).toContain(
      'ON "template_twin_release_attestation_keys"',
    );
    expect(finalHardeningMigration).toContain(
      "template_twin_verify_release_admin_session",
    );
    expect(finalHardeningMigration).toContain("TO quillmd_release_control");
    expect(adminFreshness).toContain(
      "template_twin_verify_release_admin_session",
    );
    expect(sharedAuth).toContain("usesDedicatedTemplateTwinSessionVerifier");
  });
});

describe("Template Twin release admin route boundary", () => {
  it("uses the dedicated admin gate, strict same-origin JSON, a byte ceiling, and no authority mutation", () => {
    expect(route).toContain("adminApi(");
    expect(route).toContain('request.headers.get("host")');
    expect(route).toContain('request.headers.get("origin")');
    expect(route).toContain("MAX_BODY_BYTES");
    expect(route).toContain('action: z.literal("record_approval")');
    expect(route).not.toMatch(
      /grant_authority|create_authority|assign_authority/iu,
    );
  });

  it("routes only exact control paths to the credential-isolated process", () => {
    expect(caddy).toContain("@templateTwinControlApi path");
    expect(caddy).toContain("@templateTwinControlPage path");
    expect(caddy).toContain(
      "reverse_proxy template-twin-admin-control:3011",
    );
    expect(caddy.indexOf("@templateTwinControlApi path")).toBeLessThan(
      caddy.indexOf("@adminApi path"),
    );
    expect(caddy.indexOf("@templateTwinControlPage path")).toBeLessThan(
      caddy.indexOf("@adminPath path"),
    );
    expect(compose).toContain("template-twin-admin-control:");
    expect(compose).toContain("template-twin-audit-dispatcher:");
    expect(compose).toContain(
      'QUILLMD_SERVICE_ROLE: template-twin-admin-control',
    );
    expect(compose).toContain(
      'QUILLMD_SERVICE_ROLE: template-twin-audit-dispatcher',
    );
    expect(compose).toContain('TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL: ""');
    expect(compose.match(/^\s+DB_PASSWORD: ""$/gmu)).toHaveLength(4);
    expect(compose.match(/^\s+DB_RUNTIME_PASSWORD: ""$/gmu)).toHaveLength(4);
    expect(
      compose.match(/^\s+DB_RELEASE_SECURITY_PASSWORD: ""$/gmu),
    ).toHaveLength(5);
    for (const variable of [
      "TEMPLATE_TWIN_APP_RUNTIME_ATTESTATION",
      "TEMPLATE_TWIN_ADMIN_CONTROL_RUNTIME_ATTESTATION",
      "TEMPLATE_TWIN_WORKER_RUNTIME_ATTESTATION",
    ]) {
      expect(
        compose.match(new RegExp(`^\\s+${variable}: ""$`, "gmu")),
      ).toHaveLength(4);
    }
    const adminBlock = compose.slice(
      compose.indexOf("  template-twin-admin-control:"),
      compose.indexOf(
        "  # ── DB Migrator",
        compose.indexOf("  template-twin-admin-control:"),
      ),
    );
    expect(adminBlock).toContain("env_file: []");
    expect(adminBlock).not.toContain("<<: *transcribe_md_app_environment");
    expect(adminBlock).toContain(
      "DATABASE_URL: postgresql://meddoc_release_control:",
    );
    expect(adminBlock).not.toContain("postgresql://meddoc_runtime:");
    expect(adminBlock).not.toContain("${ANTHROPIC_API_KEY}");
    expect(adminBlock).not.toContain("${DEEPGRAM_API_KEY}");
    expect(adminBlock).toContain("/api/admin/template-twin/control-health");
    expect(roleBootstrap).toContain(
      "DB_RELEASE_CONTROL_PASSWORD is required",
    );
    expect(roleBootstrap).toContain(
      "DB_AUDIT_DISPATCHER_PASSWORD is required",
    );
    expect(releaseSecurityBootstrap).toContain(
      "DB_RELEASE_SECURITY_PASSWORD is required",
    );
    expect(releaseSecurityBootstrap).toContain(
      "GRANT quillmd_release_security TO meddoc_release_security",
    );
  });
});
