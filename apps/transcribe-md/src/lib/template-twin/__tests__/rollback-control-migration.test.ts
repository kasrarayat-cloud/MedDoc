import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = path.resolve(__dirname, "../../../../../..");
const migration = readFileSync(
  path.join(
    ROOT,
    "packages/db/prisma/migrations/20260719130000_template_twin_rollback_fence_v1/migration.sql",
  ),
  "utf8",
);
const integrityMigration = readFileSync(
  path.join(
    ROOT,
    "packages/db/prisma/migrations/20260719140000_template_twin_rollback_fence_integrity_v2/migration.sql",
  ),
  "utf8",
);
const linearizationMigration = readFileSync(
  path.join(
    ROOT,
    "packages/db/prisma/migrations/20260719150000_template_twin_rollback_fence_linearization_v3/migration.sql",
  ),
  "utf8",
);
const fillIdentityMigration = readFileSync(
  path.join(
    ROOT,
    "packages/db/prisma/migrations/20260719153000_template_twin_fill_identity_immutability_v4/migration.sql",
  ),
  "utf8",
);
const fillOwnerLineageMigration = readFileSync(
  path.join(
    ROOT,
    "packages/db/prisma/migrations/20260719164500_template_twin_fill_owner_lineage_immutability_v5/migration.sql",
  ),
  "utf8",
);
const route = readFileSync(
  path.join(
    ROOT,
    "apps/transcribe-md/src/app/api/admin/template-twin/rollback/route.ts",
  ),
  "utf8",
);
const service = readFileSync(
  path.join(
    ROOT,
    "apps/transcribe-md/src/lib/template-twin/rollback-control.ts",
  ),
  "utf8",
);

describe("Template Twin rollback-control migration contract", () => {
  it("is additive, default-open as a fence, and leaves rollout default-off", () => {
    expect(migration).toMatch(/\bBEGIN;[\s\S]*\bCOMMIT;\s*$/u);
    expect(migration).toContain("SET LOCAL lock_timeout = '2s'");
    expect(migration).toContain("SET LOCAL statement_timeout = '30s'");
    expect(migration).toContain(
      'CREATE TABLE "template_twin_rollback_operations"',
    );
    expect(migration).toContain(
      "ADD COLUMN \"rollbackFenceState\" TEXT NOT NULL DEFAULT 'OPEN'",
    );
    expect(migration).not.toMatch(
      /UPDATE\s+"template_twin_rollout_controls"[\s\S]*?"enabled"\s*=\s*true/iu,
    );
    expect(migration).not.toMatch(/UPDATE\s+"practices"/iu);
  });

  it("enforces monotonic fence transitions and prevents enablement while fenced", () => {
    for (const evidence of [
      "Template Twin rollback fence generation cannot decrease",
      "Template Twin rollback fence transition is invalid",
      "Template Twin rollback fence metadata cannot change without a transition",
      "Template Twin rollback fence operation linkage is immutable",
      "Template Twin cannot be enabled while rollback is fenced",
      "Template Twin practice cannot be enabled while rollback is fenced",
      "OLD.\"rollbackFenceState\" = 'PREPARED'",
      "NEW.\"rollbackFenceState\" IN ('OPEN', 'REVOKED')",
    ]) {
      expect(migration).toContain(evidence);
    }
  });

  it("makes rollback operation identity and terminal history immutable", () => {
    for (const evidence of [
      "template_twin_guard_rollback_operation_history",
      "BEFORE INSERT OR UPDATE OR DELETE",
      "Template Twin rollback operation must start prepared",
      "Template Twin rollback operation identity is immutable",
      "Template Twin rollback operation transition is invalid",
      "Template Twin rollback operation history cannot be deleted",
      "OLD.\"state\" IS DISTINCT FROM 'PREPARED'",
      "NEW.\"state\" NOT IN ('REVOKED', 'CANCELLED')",
    ]) {
      expect(migration).toContain(evidence);
    }
  });

  it("commit-fences the singleton, operation state, audit evidence, and active versions", () => {
    expect(integrityMigration).toMatch(/\bBEGIN;[\s\S]*\bCOMMIT;\s*$/u);
    for (const evidence of [
      "template_twin_rollout_singleton_insert_delete_guard",
      "template_twin_rollout_singleton_identity_guard",
      "template_twin_rollout_singleton_truncate_guard",
      "template_twin_rollback_operation_truncate_guard",
      "DEFERRABLE INITIALLY DEFERRED",
      "Template Twin prepared fence must link a prepared operation",
      "Template Twin revoked fence must link a revoked operation",
      "Template Twin prepared operation must own the fence",
      "Template Twin rollback operation audit evidence is missing",
      "Template Twin version cannot be activated while rollback is fenced",
      "aa_template_twin_active_version_rollback_insert_guard",
      "aa_template_twin_active_version_rollback_update_guard",
    ]) {
      expect(integrityMigration).toContain(evidence);
    }
  });

  it("requires all physician, synthetic, automation, and provider work to drain before a revoked fence can commit", () => {
    for (const evidence of [
      "Template Twin revoked fence requires fill work drained",
      "Template Twin revoked fence requires pinned visits drained",
      "Template Twin revoked fence requires synthetic work drained",
      "Template Twin revoked fence requires provider work drained",
      "Template Twin revoked fence requires automation work drained",
      "'RESOLVING', 'NEEDS_REVIEW', 'VERIFIED'",
      "'RESERVED', 'IN_FLIGHT', 'UNKNOWN_OUTCOME'",
      "'PENDING', 'RUNNING'",
    ]) {
      expect(integrityMigration).toContain(evidence);
    }
  });

  it("linearizes every drain-inventory entry path with the rollback control", () => {
    expect(linearizationMigration).toMatch(
      /\bBEGIN;[\s\S]*\bCOMMIT;\s*$/u,
    );
    for (const evidence of [
      "template_twin_acquire_rollback_linearization_lock",
      "pg_advisory_xact_lock(73119, 20260719)",
      "aaa_template_twin_rollout_control_linearization_lock",
      "aa_template_twin_practice_rollback_insert_guard",
      "aa_template_twin_fill_rollback_insert_guard",
      "aa_template_twin_visit_rollback_insert_guard",
      "aa_template_twin_synthetic_run_rollback_insert_guard",
      "aa_template_twin_synthetic_admission_rollback_insert_guard",
      "aa_template_twin_manifest_rollback_insert_guard",
      "aa_template_twin_provider_rollback_insert_guard",
    ]) {
      expect(linearizationMigration).toContain(evidence);
    }
  });

  it("makes unsigned fill tenant, visit, and compiled-template lineage immutable", () => {
    expect(fillIdentityMigration).toMatch(
      /\bBEGIN;[\s\S]*SET LOCAL lock_timeout = '2s'[\s\S]*\bCOMMIT;\s*$/u,
    );
    for (const evidence of [
      "template_twin_guard_fill_identity_immutable_v4",
      "aaa_template_twin_fill_identity_immutability_v4",
      "Template Twin fill identity is immutable",
      'OLD."practiceId" IS DISTINCT FROM NEW."practiceId"',
      'OLD."visitId" IS DISTINCT FROM NEW."visitId"',
      'OLD."compiledVersionId" IS DISTINCT FROM NEW."compiledVersionId"',
      'OLD."noteTemplateId" IS DISTINCT FROM NEW."noteTemplateId"',
      'OLD."noteTemplateVersion" IS DISTINCT FROM NEW."noteTemplateVersion"',
    ]) {
      expect(fillIdentityMigration).toContain(evidence);
    }
    expect(fillIdentityMigration).toMatch(
      /BEFORE UPDATE OF[\s\S]*"practiceId"[\s\S]*"visitId"[\s\S]*"compiledVersionId"[\s\S]*"noteTemplateId"[\s\S]*"noteTemplateVersion"/u,
    );
  });

  it("freezes transitive physician ownership and the fill primary identity", () => {
    expect(fillOwnerLineageMigration).toMatch(
      /\bBEGIN;[\s\S]*SET LOCAL lock_timeout = '2s'[\s\S]*\bCOMMIT;\s*$/u,
    );
    for (const evidence of [
      "Existing Template Twin fill physician tenant lineage mismatch",
      "template_twin_fill_visit_owner_lineage_v5",
      "template_twin_assert_fill_visit_owner_lineage_v5",
      "aaa_template_twin_fill_visit_owner_lineage_v5",
      "template_twin_guard_visit_fill_owner_lineage_v5",
      "aaa_template_twin_visit_fill_owner_lineage_v5",
      "Template Twin visit physician ownership is immutable",
      "template_twin_guard_physician_fill_practice_v5",
      "aaa_template_twin_physician_fill_practice_v5",
      "Template Twin physician practice ownership is immutable",
      "template_twin_guard_fill_primary_identity_v5",
      "aaa_template_twin_fill_primary_identity_v5",
      "Template Twin fill primary identity is immutable",
      "template_twin_require_read_committed_lineage",
      "pg_advisory_xact_lock",
    ]) {
      expect(fillOwnerLineageMigration).toContain(evidence);
    }
    expect(fillOwnerLineageMigration).toMatch(
      /LOCK TABLE[\s\S]*"template_twin_fill_manifests"[\s\S]*"transcribe_visits"[\s\S]*"users"[\s\S]*IN SHARE ROW EXCLUSIVE MODE/u,
    );
    expect(fillOwnerLineageMigration).toMatch(
      /BEFORE INSERT ON "template_twin_fill_manifests"/u,
    );
    expect(fillOwnerLineageMigration).toMatch(
      /BEFORE UPDATE OF "userId" ON "transcribe_visits"/u,
    );
    expect(fillOwnerLineageMigration).toMatch(
      /BEFORE UPDATE OF "practiceId" ON "users"/u,
    );
    expect(fillOwnerLineageMigration).toMatch(
      /BEFORE UPDATE OF "id" ON "template_twin_fill_manifests"/u,
    );
  });

  it("binds complete rollback history to exact immutable audit receipts", () => {
    for (const evidence of [
      'ADD COLUMN "templateTwinOutboxEventKey" TEXT',
      "audit_logs_template_twin_outbox_event_fkey",
      "Template Twin rollback outbox evidence cannot be deleted",
      "Template Twin delivered rollback receipt is immutable",
      "Template Twin rollback audit receipt cannot be deleted",
      "Template Twin rollback audit evidence cannot be truncated",
      "Template Twin delivered rollback audit receipt is missing",
      "Template Twin rollback operation audit history is incomplete",
      "'prepared'::TEXT AS stage",
      "WHERE operation.\"state\" IN ('CANCELLED', 'REVOKED')",
    ]) {
      expect(linearizationMigration).toContain(evidence);
    }
    expect(service).toContain("missingRollbackAuditReceipts");
    expect(service).toContain('isolationLevel: "RepeatableRead"');
  });

  it("does not mutate visits, fills, signed evidence, audit history, or object lineage", () => {
    for (const table of [
      "transcribe_visits",
      "template_twin_fill_manifests",
      "audit_logs",
      "template_twin_object_ledgers",
      "template_twin_source_artifacts",
      "template_twin_certifications",
    ]) {
      expect(migration).not.toMatch(
        new RegExp(`(?:UPDATE|DELETE\\s+FROM|TRUNCATE)\\s+"${table}"`, "iu"),
      );
      expect(integrityMigration).not.toMatch(
        new RegExp(`(?:UPDATE|DELETE\\s+FROM|TRUNCATE)\\s+"${table}"`, "iu"),
      );
    }
  });

  it("exposes only a fresh SUPER_ADMIN-gated, same-origin mutation route", () => {
    expect(route).toContain('adminApi("template-twin:rollback:inspect"');
    expect(route).toContain('adminApi(\n  "template-twin:rollback:mutate"');
    expect(route).toContain("isSameOriginTemplateTwinMutation(req)");
    expect(route).toContain('z.literal("FENCE_TEMPLATE_TWIN")');
    expect(route).toContain('z.literal("REVOKE_TEMPLATE_TWIN")');
    expect(route).toContain('z.literal("REOPEN_TEMPLATE_TWIN_FENCE")');
  });

  it("scopes execute mutations to Template Twin activation and rollout columns", () => {
    expect(service).toContain(
      "WHERE \"templateKind\" = 'template_twin_docx' AND \"status\" = 'active'",
    );
    expect(service).toContain("SET \"status\" = 'inactive'");
    expect(service).toContain('SET "templateTwinEnabled" = false');
    expect(service).toContain('SET "enabled" = false');
    expect(service).not.toMatch(
      /UPDATE\s+"template_twin_fill_manifests"|UPDATE\s+"transcribe_visits"/iu,
    );
  });
});
