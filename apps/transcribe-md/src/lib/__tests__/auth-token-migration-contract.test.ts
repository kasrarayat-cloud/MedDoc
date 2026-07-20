import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const migration = readFileSync(
  resolve(
    process.cwd(),
    "../../packages/db/prisma/migrations/20260720150000_auth_token_linearization_v5/migration.sql",
  ),
  "utf8",
);

describe("auth-token linearization migration contract", () => {
  it("fails closed by retiring every historical duplicate except the newest", () => {
    expect(migration).toMatch(/PARTITION BY "userId", "purpose"/u);
    expect(migration).toMatch(/ORDER BY "createdAt" DESC, "id" DESC/u);
    expect(migration).toMatch(/WHERE "usedAt" IS NULL/u);
    expect(migration).toMatch(/ranked\.ordinal > 1/u);
    expect(migration).toMatch(/SET "usedAt" = CURRENT_TIMESTAMP/u);
  });

  it("installs the one-current-token invariant as a partial unique index", () => {
    expect(migration).toMatch(
      /CREATE UNIQUE INDEX "auth_tokens_one_unused_per_user_purpose"/u,
    );
    expect(migration).toMatch(/ON "auth_tokens" \("userId", "purpose"\)/u);
    expect(migration).toMatch(/WHERE "usedAt" IS NULL/u);
  });

  it("bounds migration lock and statement waits", () => {
    expect(migration).toContain("SET LOCAL lock_timeout = '5s'");
    expect(migration).toContain("SET LOCAL statement_timeout = '60s'");
  });
});
