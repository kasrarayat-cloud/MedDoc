import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const repositoryRoot = resolve(process.cwd(), "../..");
const read = (relativePath: string): string =>
  readFileSync(resolve(repositoryRoot, relativePath), "utf8");

describe("MFA enrollment audit semantics v7", () => {
  it("adds a distinct enum value and reserves MFA_ENABLED for verification", () => {
    const migration = read(
      "packages/db/prisma/migrations/20260720183000_mfa_enrollment_audit_semantics_v7/migration.sql",
    );
    const schema = read("packages/db/prisma/schema.prisma");
    const enroll = read("apps/transcribe-md/src/app/api/mfa/enroll/route.ts");
    const verify = read(
      "apps/transcribe-md/src/app/api/mfa/verify-enrollment/route.ts",
    );

    expect(migration).toContain(
      "ADD VALUE IF NOT EXISTS 'MFA_ENROLLMENT_STARTED'",
    );
    expect(schema).toContain("MFA_ENROLLMENT_STARTED");
    expect(enroll).toContain('action: "MFA_ENROLLMENT_STARTED"');
    expect(enroll).not.toContain('action: "MFA_ENABLED"');
    expect(verify).toContain('action: "MFA_ENABLED"');
  });
});
