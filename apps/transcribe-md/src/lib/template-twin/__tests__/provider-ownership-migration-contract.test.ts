import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const migration = readFileSync(
  path.resolve(
    process.cwd(),
    "../../packages/db/prisma/migrations/20260719171000_template_twin_provider_ownership_v1/migration.sql",
  ),
  "utf8",
);

describe("Template Twin provider ownership B-017 migration contract", () => {
  it("is additive, bounded, and never infers historical provider success", () => {
    expect(migration).toContain("SET LOCAL lock_timeout = '5s'");
    expect(migration).toContain("SET LOCAL statement_timeout = '60s'");
    expect(migration).toContain(
      'CREATE TABLE "template_twin_provider_executions"',
    );
    expect(migration).not.toMatch(
      /UPDATE\s+"template_twin_(?:source_artifacts|compiled_versions|fill_manifests|static_assets|custom_example_executions)"/iu,
    );
    expect(migration).not.toMatch(/SET\s+"status"\s*=\s*'SUCCEEDED'/iu);
  });

  it("binds logical work independently from provider and runtime selection", () => {
    expect(migration).toContain("template-twin-provider-ownership-v1");
    expect(migration).toContain("template-twin-provider-idempotency-v1");
    expect(migration).toContain("template-twin-provider-runtime-v1");
    expect(migration).toContain(
      "TEMPLATE_TWIN_PROVIDER_EXECUTION_IDENTITY_INVALID",
    );
    expect(migration).toContain(
      'CREATE UNIQUE INDEX "template_twin_provider_execution_ownership_key"',
    );
    const ownershipExpression = migration.slice(
      migration.indexOf("expected_owner :="),
      migration.indexOf("expected_idempotency :="),
    );
    expect(ownershipExpression).not.toMatch(
      /NEW\."(?:provider|providerMode|model|providerConfigurationSha256|runtimeIdentitySha256)"/u,
    );
  });

  it("enforces one-owner CAS, terminal ambiguity, and immutable identities", () => {
    expect(migration).toContain(
      "TEMPLATE_TWIN_PROVIDER_EXECUTION_CLAIM_INVALID",
    );
    expect(migration).toContain(
      "TEMPLATE_TWIN_PROVIDER_EXECUTION_TERMINAL_IMMUTABLE",
    );
    expect(migration).toContain("UNKNOWN_OUTCOME");
    expect(migration).toContain('"invocationCount" = 1');
    expect(migration).toContain(
      'NEW."claimId" IS DISTINCT FROM OLD."claimId"',
    );
  });

  it("requires an exact approved release, practice epoch, and runtime for LIVE claims", () => {
    expect(migration).toContain(
      "TEMPLATE_TWIN_PROVIDER_RUNTIME_NOT_AUTHORIZED",
    );
    expect(migration).toContain(
      "public.template_twin_release_approvals_are_current",
    );
    expect(migration).toContain(
      "public.template_twin_release_runtime_ready",
    );
    expect(migration).toContain(
      'global_control."generation" = NEW."pinnedGlobalRolloutGeneration"',
    );
    expect(migration).toContain(
      'practice."templateTwinRolloutGeneration" =',
    );
    expect(migration).toContain(
      'runtime."instanceId" = NEW."runtimeInstanceId"',
    );
  });

  it("makes downstream artifacts consume canonical successful receipts", () => {
    for (const table of [
      "template_twin_source_artifacts",
      "template_twin_compiled_versions",
      "template_twin_fill_manifests",
      "template_twin_static_assets",
      "template_twin_custom_example_executions",
    ]) {
      expect(migration).toContain(`ALTER TABLE "${table}"`);
    }
    expect(migration).toContain(
      "template-twin-provider-ownership-receipt-v1",
    );
    expect(migration).toContain(
      'execution."status" = \'SUCCEEDED\'',
    );
    expect(migration).toContain(
      "TEMPLATE_TWIN_PROVIDER_RECEIPT_REQUIRED",
    );
    expect(migration).toContain(
      "TEMPLATE_TWIN_PROVIDER_RECEIPT_IMMUTABLE",
    );
    expect(migration).toContain("SOURCE_PHI_SCAN");
    expect(migration).toContain("SOURCE_SEMANTIC_MAPPING");
    expect(migration).toContain("L1_TRANSCRIBE");
    expect(migration).toContain("L1B_TRANSCRIBE");
    expect(migration).toContain("L2_SPEAKER_ROLES");
    expect(migration).toContain("L3_EXTRACT_ENTITIES");
    expect(migration).toContain("L4_GENERATE_SOAP");
    expect(migration).toContain("L5_SELF_CRITIQUE");
  });

  it("does not grant deletion or expose private payload and claim fields", () => {
    expect(migration).toContain(
      'REVOKE DELETE, TRUNCATE ON "template_twin_provider_executions"',
    );
    expect(migration).not.toMatch(
      /GRANT\s+(?:ALL|DELETE|TRUNCATE)[\s\S]{0,100}"template_twin_provider_executions"[\s\S]{0,50}quillmd_runtime/iu,
    );
    expect(migration).toContain(
      "claimId are prohibited from clients, logs, audit metadata, and screenshots",
    );
  });
});
