import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = path.resolve(__dirname, "../../../../../..");
const migration = readFileSync(
  path.join(
    ROOT,
    "packages/db/prisma/migrations/20260719133000_template_twin_completed_candidate_review_preview_v1/migration.sql",
  ),
  "utf8",
);
const postgresContract = readFileSync(
  path.join(
    ROOT,
    "apps/transcribe-md/scripts/template-twin-completed-candidate-review-preview-contract.sql",
  ),
  "utf8",
);

describe("completed-candidate review-preview migration contract", () => {
  it("is additive, time-bounded, and never activates a note template", () => {
    expect(migration).toMatch(/\bBEGIN;[\s\S]*\bCOMMIT;\s*$/u);
    expect(migration).toContain("SET LOCAL lock_timeout = '2s'");
    expect(migration).toContain("SET LOCAL statement_timeout = '30s'");
    expect(migration).toContain(
      'CREATE TABLE "template_twin_completed_candidate_review_receipts"',
    );
    expect(migration).not.toMatch(
      /(?:INSERT\s+INTO|UPDATE|ALTER\s+TABLE)\s+"note_templates"/iu,
    );
    expect(migration).not.toMatch(/\bDELETE\s+FROM\b/iu);
  });

  it("binds a redacted projection to exact source, candidate, and relational identities", () => {
    for (const evidence of [
      "completed-document-candidate/1.1.0",
      "completed-candidate-redacted-structural-review/1.0.0",
      "NEW.\"reviewProjection\"->'sourceExampleSha256s'",
      "NEW.\"reviewProjection\"->>'sourceStructureSha256'",
      "NEW.\"reviewProjection\"->>'candidateSha256'",
      "NEW.\"reviewProjection\"->>'candidateStructureSha256'",
      "NEW.\"reviewProjection\"->>'inventorySha256'",
      "Template Twin completed candidate projection block identity mismatch",
      "Template Twin completed candidate projection table identity mismatch",
      "Template Twin completed candidate projection table grid mismatch",
      "Template Twin completed candidate projection role mismatch",
      "Template Twin completed candidate projection cell topology mismatch",
      "Template Twin completed candidate projection inventory mismatch",
      "candidate_roles GROUP BY candidate_tag HAVING count(*) <> 1",
      "label_roles GROUP BY region_id HAVING count(*) <> 1",
    ]) {
      expect(migration).toContain(evidence);
    }
  });

  it("requires an exact, current, single-use 15-minute physician receipt", () => {
    for (const evidence of [
      '"expiresAt" = "createdAt" + INTERVAL \'15 minutes\'',
      '"tokenSha256" CHAR(64) NOT NULL',
      '"globalRolloutGeneration" BIGINT NOT NULL',
      '"practiceRolloutGeneration" BIGINT NOT NULL',
      "Template Twin completed candidate review receipts are append-only",
      "Template Twin completed candidate review receipt must start unused",
      'OLD."consumedAt" IS NOT NULL',
      'OLD."expiresAt" <= clock_timestamp()',
      'receipt."consumedAt" IS DISTINCT FROM NEW."reviewedAt"',
      'candidate."reviewReceiptId" IS DISTINCT FROM NEW."id"',
      "Template Twin completed candidate review receipt invalid",
      "Template Twin completed candidate review receipt mismatch",
    ]) {
      expect(migration).toContain(evidence);
    }
  });

  it("rehearses projection tamper, receipt mismatch, expiry, replay, and atomic terminal paths", () => {
    for (const evidence of [
      "candidate_structure",
      "duplicate_cell",
      "missing_label",
      "candidate_state",
      "reversed_source",
      "TT_PREVIEW_TAMPER_DID_NOT_BLOCK",
      "TT_PREVIEW_WRONG_GENERATION_DID_NOT_BLOCK",
      "TT_PREVIEW_RECEIPT_ONLY_DID_NOT_BLOCK",
      "TT_PREVIEW_UNCONSUMED_TERMINAL_DID_NOT_BLOCK",
      "TT_PREVIEW_EXPIRED_RECEIPT_DID_NOT_BLOCK",
      "TT_PREVIEW_RECEIPT_REUSE_DID_NOT_BLOCK",
      "TT_PREVIEW_VALID_TERMINAL_PATH_FAILED",
      "PASS template-twin-completed-candidate-review-preview-contract-v1",
    ]) {
      expect(postgresContract).toContain(evidence);
    }
  });
});
