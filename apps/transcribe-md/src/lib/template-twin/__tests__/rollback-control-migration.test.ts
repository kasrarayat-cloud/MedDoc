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
