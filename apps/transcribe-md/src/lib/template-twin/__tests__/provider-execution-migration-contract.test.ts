import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const migration = readFileSync(
  path.resolve(
    process.cwd(),
    "../../packages/db/prisma/migrations/20260718090000_visit_automation_provider_execution_v1/migration.sql",
  ),
  "utf8",
);

describe("provider execution migration 76 contract", () => {
  it("is an additive bounded migration with no historical success backfill", () => {
    expect(migration).toContain("SET LOCAL lock_timeout = '5s'");
    expect(migration).toContain("SET LOCAL statement_timeout = '60s'");
    expect(migration).toContain(
      'CREATE TABLE "visit_automation_provider_executions"',
    );
    expect(migration).not.toMatch(/UPDATE\s+"?transcribe_visits"?/iu);
    expect(migration).not.toMatch(
      /INSERT[\s\S]+SELECT[\s\S]+visit_automation/iu,
    );
  });

  it("enforces tenant lineage, one execution per layer, and terminal immutability", () => {
    expect(migration).toContain(
      'CONSTRAINT "visit_automation_provider_execution_layer_fkey"',
    );
    expect(migration).toContain(
      'CREATE UNIQUE INDEX "visit_automation_provider_execution_idempotency_key"',
    );
    expect(migration).toContain(
      "VISIT_AUTOMATION_PROVIDER_EXECUTION_STAGING_MISMATCH",
    );
    expect(migration).toContain(
      "VISIT_AUTOMATION_PROVIDER_EXECUTION_TERMINAL_IMMUTABLE",
    );
    expect(migration).toContain("UNKNOWN_OUTCOME");
    expect(migration).toContain('"invocationCount" = 1');
  });

  it("adds a durable, three-delivery staging retry handoff", () => {
    expect(migration).toContain('ADD COLUMN "workerDeliveryCount" INTEGER');
    expect(migration).toContain('ADD COLUMN "workerRetryReadyAt"');
    expect(migration).toContain('"status" = \'RETRY_ENQUEUED\'');
    expect(migration).toContain(
      '"workerDeliveryCount" BETWEEN 0 AND 3',
    );
    expect(migration).toContain(
      "OLD.\"status\" = 'PROCESSING' AND NEW.\"status\" = 'RETRY_ENQUEUED'",
    );
    expect(migration).toContain(
      "OLD.\"status\" = 'RETRY_ENQUEUED' AND NEW.\"status\" = 'PROCESSING'",
    );
  });
});
