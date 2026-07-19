import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const root = resolve(__dirname, "../../../../../..");
const migration = readFileSync(
  resolve(
    root,
    "packages/db/prisma/migrations/20260717230000_visit_automation_manifest_v1/migration.sql",
  ),
  "utf8",
);
const locks = readFileSync(
  resolve(root, "apps/transcribe-md/src/worker/automation-locks.ts"),
  "utf8",
);

describe("visit automation migration and lock contract", () => {
  it("keeps timeout settings transaction-local and rolls DDL back atomically", () => {
    expect(migration).toMatch(/\bBEGIN;\s*SET LOCAL lock_timeout = '5s';/u);
    expect(migration).toContain("SET LOCAL statement_timeout = '60s';");
    expect(migration.trimEnd().endsWith("COMMIT;")).toBe(true);
  });

  it("is additive and never labels a historical visit complete", () => {
    expect(migration).not.toMatch(/UPDATE\s+"?transcribe_visits"?/iu);
    expect(migration).not.toMatch(
      /INSERT\s+INTO\s+"visit_automation_manifests"/iu,
    );
    expect(migration).toContain('CREATE TABLE "visit_automation_manifests"');
    expect(migration).toContain('CREATE TABLE "visit_automation_layers"');
  });

  it("enforces manifest inventory and visit terminal state in PostgreSQL", () => {
    expect(migration).toContain("VISIT_AUTOMATION_REQUIRED_LAYER_INCOMPLETE");
    expect(migration).toContain("VISIT_AUTOMATION_PROOF_REQUIRED");
    expect(migration).toContain('COUNT(DISTINCT layer."layerId")');
    expect(migration).toContain(
      'BEFORE INSERT OR UPDATE ON "transcribe_visits"',
    );
    expect(migration).toContain("VISIT_AUTOMATION_MANIFEST_COMPLETE_IMMUTABLE");
    expect(migration).toContain("VISIT_AUTOMATION_COMPLETE_LAYER_IMMUTABLE");
    expect(migration).toContain("VISIT_AUTOMATION_LAYER_RESULT_IMMUTABLE");
    expect(migration).toContain("VISIT_AUTOMATION_MANIFEST_REBIND_INVALID");
    expect(migration).toContain(
      "OLD.\"status\" = 'COMPLETE' AND complete_reprocess",
    );
    expect(migration).toContain('visit."signedAt" IS NULL');
    for (const layerId of [
      "icd_coding",
      "cpt_coding",
      "rx_drafting",
      "referrals",
      "patient_summary",
      "em_mdm_prewarm",
    ]) {
      expect(migration).toContain(`layer.\"layerId\" = '${layerId}'`);
    }
  });

  it("publishes one canonical lock order for all affected transactions", () => {
    const ordered = [
      '"global_rollout"',
      '"practice"',
      '"staging_admission"',
      '"staging_run"',
      '"actor"',
      '"visit"',
      '"automation_manifest"',
      '"automation_layers"',
      '"provider_execution"',
      '"audit_outbox"',
    ];
    let cursor = -1;
    for (const token of ordered) {
      const next = locks.indexOf(token);
      expect(next).toBeGreaterThan(cursor);
      cursor = next;
    }
  });
});
