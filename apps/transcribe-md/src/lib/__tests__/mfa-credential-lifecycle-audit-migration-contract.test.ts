import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = resolve(process.cwd(), "../..");
const migration = readFileSync(
  resolve(
    ROOT,
    "packages/db/prisma/migrations/20260720200000_mfa_credential_lifecycle_audit_v8/migration.sql",
  ),
  "utf8",
);
const schema = readFileSync(
  resolve(ROOT, "packages/db/prisma/schema.prisma"),
  "utf8",
);
const audit = readFileSync(
  resolve(ROOT, "apps/transcribe-md/src/lib/audit.ts"),
  "utf8",
);

describe("MFA credential lifecycle audit migration", () => {
  it.each(["MFA_RECOVERY_CODES_ROTATED", "MFA_CREDENTIALS_MIGRATED"])(
    "adds and types the distinct %s receipt",
    (action) => {
      expect(migration).toContain(`ADD VALUE IF NOT EXISTS '${action}'`);
      expect(schema).toContain(action);
      expect(audit).toContain(`| "${action}"`);
    },
  );

  it("is an additive, bounded enum-only migration", () => {
    expect(migration).toContain("BEGIN;");
    expect(migration).toContain("SET LOCAL lock_timeout = '5s'");
    expect(migration).toContain("SET LOCAL statement_timeout = '30s'");
    expect(migration).not.toMatch(/\b(?:DROP|DELETE|UPDATE|TRUNCATE)\b/u);
  });
});
