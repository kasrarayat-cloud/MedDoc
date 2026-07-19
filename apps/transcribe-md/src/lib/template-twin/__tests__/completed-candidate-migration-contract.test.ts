import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = path.resolve(__dirname, "../../../../../..");
const migration = readFileSync(
  path.join(
    ROOT,
    "packages/db/prisma/migrations/20260719120000_template_twin_completed_candidate_v1/migration.sql",
  ),
  "utf8",
);

describe("completed-document candidate migration contract", () => {
  it("is additive and bounded without creating or updating an active template", () => {
    expect(migration).toMatch(/\bBEGIN;[\s\S]*\bCOMMIT;\s*$/u);
    expect(migration).toContain("SET LOCAL lock_timeout = '2s'");
    expect(migration).toContain("SET LOCAL statement_timeout = '30s'");
    expect(migration).toContain(
      'CREATE TABLE "template_twin_completed_candidates"',
    );
    expect(migration).not.toMatch(
      /(?:INSERT\s+INTO|UPDATE|ALTER\s+TABLE)\s+"note_templates"/iu,
    );
    expect(migration).not.toMatch(
      /(?:INSERT\s+INTO|UPDATE)\s+"template_twin_source_artifacts"/iu,
    );
  });

  it("binds every example to a clean isolated quarantine row in the same tenant", () => {
    for (const evidence of [
      "\"status\" = 'ISOLATED'",
      "\"intakeMode\" = 'COMPLETED_EXAMPLE'",
      'q."practiceId"',
      "quarantine_practice <> candidate_practice",
      'quarantine_lineage <> NEW."candidateId"',
      "quarantine_status <> 'ISOLATED'",
      "Template Twin isolated example has no candidate claim",
    ]) {
      expect(migration).toContain(evidence);
    }
  });

  it("requires an immutable claimed candidate object and a complete terminal review", () => {
    for (const evidence of [
      "l.\"kind\" = 'candidate'",
      "l.\"state\" = 'CLAIMED'",
      "l.\"claimType\" = 'completed_candidate'",
      'owner_sha256 IS NULL OR owner_sha256 <> NEW."sha256"',
      'owner_size_bytes IS NULL OR owner_size_bytes <> NEW."sizeBytes"',
      "Template Twin completed candidate identity is immutable",
      "Template Twin completed candidate region decision is terminal",
      "Template Twin completed candidate review inventory mismatch",
      "Template Twin completed candidate example census mismatch",
      "example_count NOT BETWEEN 2 AND 3",
      "example_structure_count <> 1",
      "candidateFieldCount')::INTEGER <> total_count",
      "total_count < 1",
      "pending_count <> 0 OR rejected_count <> 0",
      "pending_count <> 0 OR rejected_count < 1",
    ]) {
      expect(migration).toContain(evidence);
    }
  });

  it("keeps raw examples and generated candidate lineage append-only", () => {
    expect(migration).toContain(
      "Template Twin quarantine terminal state is immutable",
    );
    expect(migration).toContain(
      "Template Twin completed candidate examples are append-only",
    );
    expect(migration).toContain(
      "Template Twin completed candidate regions are append-only",
    );
  });
});
