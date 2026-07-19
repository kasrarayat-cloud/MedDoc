import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = path.resolve(__dirname, "../../../../../..");
const migration = readFileSync(
  path.join(
    ROOT,
    "packages/db/prisma/migrations/20260719123000_template_twin_activation_source_admission_v1/migration.sql",
  ),
  "utf8",
);
const postgresContract = readFileSync(
  path.join(
    ROOT,
    "apps/transcribe-md/scripts/template-twin-quarantine-certification-contract.sql",
  ),
  "utf8",
);

describe("Template Twin activation source-admission migration", () => {
  it("is bounded and additive without rewriting historical templates", () => {
    expect(migration).toMatch(/\bBEGIN;[\s\S]*\bCOMMIT;\s*$/u);
    expect(migration).toContain("SET LOCAL lock_timeout = '5s'");
    expect(migration).toContain("SET LOCAL statement_timeout = '60s'");
    expect(migration).not.toMatch(/\bUPDATE\s+"note_templates"/iu);
    expect(migration).not.toMatch(/\bDELETE\s+FROM\b/iu);
    expect(migration).toContain(
      "template_twin_active_source_admission_insert_guard",
    );
    expect(migration).toContain(
      "template_twin_active_source_admission_update_guard",
    );
  });

  it("scopes the backstop to active Twins and requires the current native admission chain", () => {
    for (const evidence of [
      `NEW."templateKind" <> 'template_twin_docx'`,
      `NEW."status" <> 'active'`,
      `c."certificationStatus" = 'CERTIFIED'`,
      `c."blockingUnsupportedCount" = 0`,
      `q."intakeMode" = 'NATIVE_TEMPLATE'`,
      `q."status" = 'ADMITTED'`,
      `q."admittedAt" >= q."scannedAt"`,
      `q."malwareScanEvidence"->>'verdict' = 'clean'`,
      "template_twin_malware_attestation_sha256",
      "template_twin_metadata_minimization_receipt_valid",
      `source_ledger."claimType" = 'source_artifact'`,
      `quarantine_ledger."claimType" = 'quarantine_artifact'`,
      `output_ledger."claimType" = 'compiled_test_output'`,
      "Template Twin activation source admission mismatch",
    ]) {
      expect(migration).toContain(evidence);
    }
  });

  it("rehearses admitted, legacy, direct-active, and ordinary-template paths", () => {
    for (const evidence of [
      "TT_QUARANTINE_ACTIVATION_CONTRACT_VALID_PATH_FAILED",
      "TT_QUARANTINE_ACTIVATION_CONTRACT_DID_NOT_BLOCK",
      "TT_QUARANTINE_DIRECT_ACTIVE_INSERT_DID_NOT_BLOCK",
      "TT_QUARANTINE_ACTIVATION_ORDINARY_PATH_REGRESSED",
      "PASS template-twin-quarantine-certification-contract-v3",
    ]) {
      expect(postgresContract).toContain(evidence);
    }
  });
});
