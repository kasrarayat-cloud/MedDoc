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
    expect(migration).toContain("template-twin-provider-ownership-v2");
    expect(migration).toContain("template-twin-provider-idempotency-v2");
    expect(migration).toContain("template-twin-provider-runtime-v1");
    expect(migration).toContain(
      "TEMPLATE_TWIN_PROVIDER_EXECUTION_IDENTITY_INVALID",
    );
    expect(migration).toContain(
      'CREATE UNIQUE INDEX "template_twin_provider_execution_ownership_key"',
    );
    const executionGuard = migration.slice(
      migration.indexOf(
        "CREATE OR REPLACE FUNCTION template_twin_provider_execution_guard_identity",
      ),
      migration.indexOf(
        "CREATE OR REPLACE FUNCTION template_twin_provider_execution_guard_transition",
      ),
    );
    const ownershipExpression = executionGuard.slice(
      executionGuard.indexOf("expected_owner :="),
      executionGuard.indexOf("expected_idempotency :="),
    );
    expect(ownershipExpression).toContain('NEW."operationInstance"');
    expect(ownershipExpression).not.toMatch(
      /NEW\."(?:actorUserId|subjectSha256|inputSha256|provider|providerMode|model|operationVersion|providerConfigurationSha256|runtimeIdentitySha256|sourceArtifactId|compiledVersionId|noteTemplateId|sourceLineageId|sourceSha256)"/u,
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
    expect(migration).toContain('NEW."claimId" IS DISTINCT FROM OLD."claimId"');
    expect(migration).toMatch(
      /OLD\."status" = 'IN_FLIGHT' AND NEW\."status" = 'UNKNOWN_OUTCOME'[\s\S]{0,220}'PROVIDER_OUTCOME_UNKNOWN'[\s\S]{0,220}'RESULT_COMMIT_AMBIGUOUS'/u,
    );
    expect(migration).toMatch(
      /IF OLD\."status" IN \('SUCCEEDED', 'FAILED', 'UNKNOWN_OUTCOME'\) THEN\s+RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_EXECUTION_TERMINAL_IMMUTABLE'/u,
    );
    expect(migration).not.toMatch(
      /IF OLD\."status" IN \('SUCCEEDED', 'FAILED', 'UNKNOWN_OUTCOME'\) THEN\s+IF NEW IS DISTINCT FROM OLD/u,
    );
  });

  it("requires an exact approved release, practice epoch, and runtime for LIVE claims", () => {
    expect(migration).toContain(
      "TEMPLATE_TWIN_PROVIDER_RUNTIME_NOT_AUTHORIZED",
    );
    expect(migration).toContain(
      "public.template_twin_release_approvals_are_current",
    );
    expect(migration).toContain("public.template_twin_release_runtime_ready");
    expect(migration).toContain(
      'global_control."generation" = NEW."pinnedGlobalRolloutGeneration"',
    );
    expect(migration).toContain('practice."templateTwinRolloutGeneration" =');
    expect(migration).toContain(
      'runtime."instanceId" = NEW."runtimeInstanceId"',
    );
  });

  it("authorizes durable N/A decisions under the same current LIVE barrier", () => {
    const decisionGuard = migration.slice(
      migration.indexOf(
        "CREATE OR REPLACE FUNCTION template_twin_provider_plan_decision_guard",
      ),
      migration.indexOf(
        "CREATE OR REPLACE FUNCTION template_twin_provider_execution_guard_identity",
      ),
    );
    expect(decisionGuard).toContain(
      "TEMPLATE_TWIN_PROVIDER_PLAN_RUNTIME_NOT_AUTHORIZED",
    );
    expect(decisionGuard).toContain(
      "public.template_twin_release_approvals_are_current",
    );
    expect(decisionGuard).toContain(
      "public.template_twin_release_runtime_ready",
    );
    expect(decisionGuard).toContain('global_control."enabled" = TRUE');
    expect(decisionGuard).toContain(
      'global_control."generation" =\n        NEW."pinnedGlobalRolloutGeneration"',
    );
    expect(decisionGuard).toContain(
      'practice."templateTwinRolloutGeneration" =',
    );
    expect(decisionGuard).toContain(
      'runtime."instanceId" = NEW."runtimeInstanceId"',
    );
    expect(decisionGuard).toContain(
      "FOR SHARE OF candidate, manifest, runtime, global_control, practice",
    );
    expect(decisionGuard).toContain(
      'NEW."runtimeIdentitySha256" <> expected_runtime',
    );
    expect(decisionGuard).toMatch(
      /IF TG_OP = 'UPDATE' THEN\s+RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_PLAN_DECISION_IMMUTABLE'/u,
    );
    expect(decisionGuard).not.toContain("NEW IS DISTINCT FROM OLD");
  });

  it("binds pre-certification voice evidence to one exact synthetic capability", () => {
    expect(migration).toContain('"preCertificationVoiceEvidence" BOOLEAN');
    expect(migration).toContain(
      "\"operation\" = 'SYNTHETIC_EVIDENCE_TRANSCRIPTION'",
    );
    expect(migration).toContain("'template-twin-synthetic-voice-subject-v1'");
    for (const identityField of [
      "audioSha256",
      "audioSizeBytes",
      "audioMimeType",
      "audioObjectKey",
      "parentAdmissionId",
      "visitId",
      "sourceArtifactId",
      "compiledVersionId",
      "noteTemplateId",
      "sourceLineageId",
      "sourceSha256",
    ]) {
      expect(migration).toContain(`'${identityField}'`);
    }
    expect(migration).toContain(
      "TEMPLATE_TWIN_PROVIDER_SYNTHETIC_ADMISSION_INVALID",
    );
    expect(migration).toContain("'AUTHORITY_REVOKED_AFTER_PROVIDER'");
    expect(migration).toContain(
      "Template Twin synthetic voice admission is immutable",
    );
    expect(migration).toContain(
      "Template Twin synthetic voice visit is immutable",
    );
    expect(migration).toContain(
      "Template Twin synthetic QA patient is immutable",
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
    expect(migration).toContain("template-twin-provider-ownership-receipt-v2");
    expect(migration).toContain('execution."actorUserId" = expected_actor_id');
    expect(migration).toContain(
      'execution."providerMode" = expected_provider_mode',
    );
    expect(migration).toContain('execution."runtimeIdentitySha256" =');
    expect(migration).toContain("execution.\"status\" = 'SUCCEEDED'");
    expect(migration).toContain("TEMPLATE_TWIN_PROVIDER_RECEIPT_REQUIRED");
    expect(migration).toContain("TEMPLATE_TWIN_PROVIDER_RECEIPT_IMMUTABLE");
    expect(migration).toContain("SOURCE_PHI_SCAN");
    expect(migration).toContain("SOURCE_SEMANTIC_MAPPING");
    expect(migration).toContain("L1_TRANSCRIBE");
    expect(migration).toContain("L1B_TRANSCRIBE");
    expect(migration).toContain("L2_SPEAKER_ROLES");
    expect(migration).toContain("L3_EXTRACT_ENTITIES");
    expect(migration).toContain("L4_GENERATE_SOAP");
    expect(migration).toContain("L5_SELF_CRITIQUE");
    expect(migration).toContain("L6_POLISH");
    expect(migration).toContain("L6_FIDELITY_VERIFY");
    expect(migration).toContain("L4_ANCHOR_VERIFY");
    expect(migration).toContain("CUSTOM_CONCEPT_EXTRACTION");
    expect(migration).toContain(
      'CREATE TABLE "template_twin_provider_plan_decisions"',
    );
    expect(migration).toContain("executionPlanSha256");
    expect(migration).toContain('execution."operationInstance" =');
  });

  it("admits only exact staging receipts and blocks their production promotion", () => {
    expect(migration).toContain("receipt_mode NOT IN ('LIVE', 'SYNTHETIC_QA')");
    expect(migration).toContain(
      "TEMPLATE_TWIN_CERTIFICATION_LIVE_PROVIDER_RECEIPT_REQUIRED",
    );
    expect(migration).toContain(
      "TEMPLATE_TWIN_ACTIVATION_LIVE_PROVIDER_RECEIPT_REQUIRED",
    );
    expect(migration).toContain(
      "template_twin_live_provider_compilation_is_valid",
    );
    expect(migration).toContain(
      "template_twin_staging_provider_compilation_is_valid",
    );
    expect(migration).toContain(
      "\"providerAuthorizationMode\" = 'SYNTHETIC_QA'",
    );
    expect(migration).toContain("\"providerAuthorizationMode\" = 'LIVE'");
    expect(migration).toMatch(
      /CREATE TRIGGER template_twin_active_live_provider_update_guard\s+[\s\S]*?BEFORE UPDATE ON "note_templates"/u,
    );
    expect(migration).not.toContain(
      'BEFORE UPDATE OF "status" ON "note_templates"\nFOR EACH ROW EXECUTE FUNCTION template_twin_require_live_provider_activation()',
    );
    expect(migration).toContain(
      "template_twin_custom_example_unowned_failure_shape_check",
    );
    expect(migration).toContain(
      `to_jsonb(NEW)->>'resultStatus' = 'extraction_rejected'`,
    );
    expect(migration).toContain(
      "carries no fabricated\n    -- successful provider receipt",
    );
  });

  it("pins the exact safe search path and revokes every helper from PUBLIC", () => {
    expect(migration).toMatch(
      /CREATE OR REPLACE FUNCTION template_twin_provider_execution_guard_identity\(\)\s+RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER\s+SET search_path = pg_catalog, public, pg_temp/u,
    );
    const functionCount = (
      migration.match(/CREATE (?:OR REPLACE )?FUNCTION/gu) ?? []
    ).length;
    const safePathCount = (
      migration.match(
        /SET search_path = pg_catalog, public, pg_temp AS \$\$/gu,
      ) ?? []
    ).length;
    expect(functionCount).toBe(20);
    expect(safePathCount).toBe(functionCount);
    for (const routine of [
      "template_twin_assert_synthetic_qa_admission_lineage",
      "template_twin_guard_synthetic_qa_admission_transition",
      "template_twin_guard_pre_cert_voice_admission_removal",
      "template_twin_guard_pre_cert_voice_visit",
      "template_twin_guard_synthetic_qa_patient",
      "template_twin_guard_synthetic_qa_patient_truncate",
      "template_twin_provider_execution_guard_identity",
      "template_twin_provider_execution_guard_transition",
      "template_twin_provider_execution_guard_live_claim",
      "template_twin_provider_execution_guard_remove",
      "template_twin_provider_plan_decision_guard",
      "template_twin_provider_receipt_is_valid",
      "template_twin_provider_receipt_has_operation",
      "template_twin_provider_receipt_plan_has",
      "template_twin_provider_receipt_plan_is_exact",
      "template_twin_guard_provider_owned_artifact",
      "template_twin_staging_provider_compilation_is_valid",
      "template_twin_live_provider_compilation_is_valid",
      "template_twin_require_live_provider_certification",
      "template_twin_require_live_provider_activation",
    ]) {
      expect(migration).toMatch(
        new RegExp(`REVOKE ALL ON FUNCTION ${routine}\\(`, "u"),
      );
    }
  });

  it("does not grant deletion or expose private payload and claim fields", () => {
    expect(migration).toContain(
      'REVOKE DELETE, TRUNCATE ON "template_twin_provider_executions"',
    );
    expect(migration).not.toMatch(
      /GRANT\s+(?:ALL|DELETE|TRUNCATE)[\s\S]{0,100}"template_twin_provider_executions"[\s\S]{0,50}quillmd_runtime/iu,
    );
    expect(migration).toContain(
      "CREATE TRIGGER template_twin_provider_plan_decision_truncate_guard_trigger",
    );
    expect(migration).toContain(
      'REVOKE UPDATE, DELETE, TRUNCATE ON "template_twin_provider_plan_decisions"',
    );
    expect(migration).toContain("TG_OP IN ('DELETE', 'TRUNCATE')");
    expect(migration).toContain(
      "claimId are prohibited from clients, logs, audit metadata, and screenshots",
    );
  });
});
