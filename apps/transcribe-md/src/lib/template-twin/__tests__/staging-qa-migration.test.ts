import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
} from "../staging-qa-fixtures";

const ROOT = path.resolve(__dirname, "../../../../../..");
const migration = readFileSync(
  path.join(
    ROOT,
    "packages/db/prisma/migrations/20260717013000_template_twin_staging_qa_v1/migration.sql",
  ),
  "utf8",
);

describe("Template Twin staging QA migration contract", () => {
  it("is additive, bounded, and does not rewrite existing clinical tables", () => {
    expect(migration).toContain("SET LOCAL lock_timeout = '2s'");
    expect(migration).toContain("SET LOCAL statement_timeout = '30s'");
    expect(migration).toContain(
      'CREATE TABLE "template_twin_synthetic_qa_runs"',
    );
    expect(migration).not.toMatch(
      /UPDATE\s+(?:"transcribe_visits"|"note_templates"|"users"|"practices")/iu,
    );
  });

  it("enforces owner, practice, patient, certified source, and exact template lineage", () => {
    for (const evidence of [
      'patient."practiceId" = NEW."practiceId"',
      'u."practiceId" = NEW."practiceId"',
      "u.\"role\" = 'DOCTOR'",
      'nt."doctorId" = u."id"',
      "nt.\"status\" = 'active'",
      "cv.\"certificationStatus\" = 'CERTIFIED'",
      'certification."compiledVersionId" = cv."id"',
      "source.\"validationStatus\" = 'accepted'",
      `source."sha256" = '${TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256}'`,
      `source."sizeBytes" = ${TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES}`,
      'v."noteTemplateVersion" = NEW."noteTemplateVersion"',
    ]) {
      expect(migration).toContain(evidence);
    }
  });

  it("keeps visit ownership and immutable template pins protected after admission", () => {
    expect(migration).toContain(
      "CREATE TRIGGER template_twin_synthetic_qa_run_lineage_guard",
    );
    expect(migration).toContain(
      "CREATE TRIGGER template_twin_synthetic_qa_visit_pin_guard",
    );
    expect(migration).toContain(
      "Template Twin synthetic QA visit provenance is immutable",
    );
    for (const protectedColumn of [
      '"patientId"',
      '"patientName"',
      '"inputMode"',
      '"rawTextInput"',
      '"dictationAudioKey"',
      '"audioMimeType"',
      '"audioSizeBytes"',
    ]) {
      expect(migration).toContain(protectedColumn);
    }
    expect(migration).toContain(
      "CREATE TRIGGER template_twin_synthetic_qa_patient_guard",
    );
  });

  it("makes admission identity immutable and attempts monotonic", () => {
    expect(migration).toContain(
      "CREATE TRIGGER template_twin_synthetic_qa_run_transition_guard",
    );
    for (const immutable of [
      'NEW."requestSha256"',
      'NEW."payloadSha256"',
      'NEW."mode"',
      'NEW."fixtureVersion"',
      'NEW."pinnedGlobalRolloutGeneration"',
      'NEW."pinnedPracticeRolloutGeneration"',
    ]) {
      expect(migration).toContain(immutable);
    }
    expect(migration).toContain('NEW."attempt" > OLD."attempt" + 1');
    expect(migration).toContain(
      "OLD.\"status\" = 'PROCESSING' AND NEW.\"status\" IN ('COMPLETED', 'PROCESSING_FAILED')",
    );
  });

  it("makes stalled-worker reclaim lease-bound and terminal ownership immutable", () => {
    for (const column of [
      '"workerClaimId" VARCHAR(64)',
      '"workerClaimedAt" TIMESTAMPTZ(6)',
      '"workerHeartbeatAt" TIMESTAMPTZ(6)',
      '"workerLeaseExpiresAt" TIMESTAMPTZ(6)',
    ]) {
      expect(migration).toContain(column);
    }
    expect(migration).toContain(
      'OLD."workerLeaseExpiresAt" > clock_timestamp()',
    );
    expect(migration).not.toContain(
      'OLD."workerLeaseExpiresAt" > CURRENT_TIMESTAMP',
    );
    expect(migration).toContain(
      "Template Twin synthetic QA worker lease is still active",
    );
    expect(migration).toContain(
      "Template Twin synthetic QA terminal worker claim changed",
    );
  });
});
