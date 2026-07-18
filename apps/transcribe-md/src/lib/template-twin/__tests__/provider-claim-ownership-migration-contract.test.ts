import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const migration = readFileSync(
  path.resolve(
    process.cwd(),
    "../../packages/db/prisma/migrations/20260718180000_visit_automation_provider_claim_ownership_v1/migration.sql",
  ),
  "utf8",
);
const implementation = readFileSync(
  path.resolve(process.cwd(), "src/worker/provider-execution.ts"),
  "utf8",
);
const dataMigration = migration.slice(
  0,
  migration.indexOf(
    "CREATE OR REPLACE FUNCTION visit_automation_provider_execution_guard_transition",
  ),
);

describe("provider claim ownership migration 77 contract", () => {
  it("adds a bounded internal concurrency token without inferring success", () => {
    expect(migration).toContain("SET LOCAL lock_timeout = '5s'");
    expect(migration).toContain("SET LOCAL statement_timeout = '60s'");
    expect(migration).toContain('ADD COLUMN "claimId" CHAR(64)');
    expect(migration).toContain('ADD COLUMN "claimedAt" TIMESTAMPTZ(6)');
    expect(migration).toContain(
      'CREATE UNIQUE INDEX "visit_automation_provider_execution_claim_key"',
    );
    expect(dataMigration).not.toMatch(/SET\s+"status"\s*=\s*'SUCCEEDED'/iu);
  });

  it("conservatively blocks executions that were in flight during upgrade", () => {
    expect(migration).toContain(
      '"status" = \'UNKNOWN_OUTCOME\'::"VisitAutomationProviderExecutionStatus"',
    );
    expect(migration).toContain(
      "\"failureCode\" = 'PROVIDER_OUTCOME_AMBIGUOUS'",
    );
    expect(migration).toContain(
      "VISIT_AUTOMATION_PROVIDER_EXECUTION_TERMINAL_IMMUTABLE",
    );
  });

  it("requires claim identity to survive every active-to-terminal transition", () => {
    expect(migration).toContain(
      "VISIT_AUTOMATION_PROVIDER_EXECUTION_CLAIM_INVALID",
    );
    expect(migration).toContain('NEW."claimId" IS DISTINCT FROM OLD."claimId"');
    expect(migration).toContain(
      'NEW."claimedAt" IS DISTINCT FROM OLD."claimedAt"',
    );
    expect(migration).toContain(
      '"status" = \'IN_FLIGHT\'\n      AND "invocationCount" = 1',
    );
  });

  it("uses compare-and-set ownership and claim-matched terminal writes", () => {
    expect(implementation).toContain(
      'AND "status" = \'RESERVED\'::"VisitAutomationProviderExecutionStatus"',
    );
    expect(implementation).toContain('AND "claimId" IS NULL');
    expect(implementation).toContain('kind: "CLAIMED_BY_CALLER"');
    expect(implementation).toMatch(
      /status:\s*"IN_FLIGHT",\s*\n\s*claimId:\s*input\.claim\.claimId/gu,
    );
    expect(implementation).not.toMatch(/metadata\s*:[\s\S]{0,200}claimId/gu);
  });
});
