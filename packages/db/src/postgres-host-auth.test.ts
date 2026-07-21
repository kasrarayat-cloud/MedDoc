import { describe, expect, it, vi } from "vitest";

import {
  QUILLMD_POSTGRES_HBA_CONTRACT,
  assertPostgresHostAuthenticationContract,
} from "./postgres-host-auth";

function row(
  overrides: Readonly<Record<string, string | boolean | null>> = {},
) {
  return {
    contractPath: QUILLMD_POSTGRES_HBA_CONTRACT.path,
    contractSha256: QUILLMD_POSTGRES_HBA_CONTRACT.sha256,
    passwordEncryption: QUILLMD_POSTGRES_HBA_CONTRACT.passwordEncryption,
    tcpSession: true,
    initialConfigGeneration: true,
    ...overrides,
  };
}

describe("PostgreSQL host-authentication session contract", () => {
  it("accepts only the exact mounted HBA identity over TCP", async () => {
    const prisma = { $queryRaw: vi.fn().mockResolvedValue([row()]) };

    await expect(
      assertPostgresHostAuthenticationContract({ prisma }),
    ).resolves.toBeUndefined();
    expect(prisma.$queryRaw).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["missing row", []],
    ["duplicate row", [row(), row()]],
    ["missing path", [row({ contractPath: null })]],
    ["wrong path", [row({ contractPath: "/unreviewed/pg_hba.conf" })]],
    ["missing hash", [row({ contractSha256: null })]],
    ["wrong hash", [row({ contractSha256: "0".repeat(64) })]],
    ["weaker verifier default", [row({ passwordEncryption: "md5" })]],
    ["socket session", [row({ tcpSession: false })]],
    [
      "reloaded configuration generation",
      [row({ initialConfigGeneration: false })],
    ],
  ])("rejects %s", async (_label, rows) => {
    const prisma = { $queryRaw: vi.fn().mockResolvedValue(rows) };

    await expect(
      assertPostgresHostAuthenticationContract({ prisma }),
    ).rejects.toThrow("Exact PostgreSQL host authentication is required.");
  });

  it("leaves driver failures for the fixed-output startup caller to normalize", async () => {
    const failure = new Error("synthetic driver failure");
    const prisma = {
      $queryRaw: vi.fn().mockRejectedValue(failure),
    };

    await expect(
      assertPostgresHostAuthenticationContract({ prisma }),
    ).rejects.toBe(failure);
  });
});
