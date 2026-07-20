// ============================================================================
// Unit tests for T-M16.2 auth-tokens library
// ----------------------------------------------------------------------------
// Pure helpers (generate / hash) get tested directly. DB-touching helpers
// (createAuthToken / consumeAuthToken / invalidateAuthTokens) mock the
// @meddoc/db module so we can verify the exact Prisma call shapes + the
// atomicity/expiry/purpose guards without a real database.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  mockCreate,
  mockFindUnique,
  mockFindMany,
  mockUpdateMany,
  mockUserFind,
  mockQueryRaw,
  mockTransaction,
} = vi.hoisted(() => ({
  mockCreate: vi.fn(),
  mockFindUnique: vi.fn(),
  mockFindMany: vi.fn(),
  mockUpdateMany: vi.fn(),
  mockUserFind: vi.fn(),
  mockQueryRaw: vi.fn(),
  mockTransaction: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    authToken: {
      create: mockCreate,
      findUnique: mockFindUnique,
      findMany: mockFindMany,
      updateMany: mockUpdateMany,
    },
    user: { findUnique: mockUserFind },
    $queryRaw: mockQueryRaw,
    $transaction: mockTransaction,
  },
}));

import {
  AuthTokenAuthorityError,
  consumeAuthToken,
  createAuthToken,
  generateRawToken,
  hashToken,
  invalidateAuthTokens,
} from "@/lib/auth-tokens";

const LOCKED_USER = {
  id: "u1",
  email: "synthetic@example.test",
  isActive: true,
  deactivatedAt: null,
  suspendedAt: null,
  softDeletedAt: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  mockUserFind.mockResolvedValue({
    id: "u1",
    email: "synthetic@example.test",
    name: "Synthetic User",
    isActive: true,
    deactivatedAt: null,
    suspendedAt: null,
    softDeletedAt: null,
  });
  mockFindMany.mockResolvedValue([{ id: "tk1" }]);
  mockQueryRaw.mockImplementation(
    (query: { strings?: readonly string[]; values?: readonly unknown[] }) => {
      const sql = query.strings?.join("") ?? "";
      if (sql.includes('FROM "users"')) {
        return Promise.resolve([
          { ...LOCKED_USER, id: String(query.values?.[0]) },
        ]);
      }
      return Promise.resolve([{ id: query.values?.[0] }]);
    },
  );
  mockTransaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        authToken: {
          create: mockCreate,
          findUnique: mockFindUnique,
          findMany: mockFindMany,
          updateMany: mockUpdateMany,
        },
        user: { findUnique: mockUserFind },
        $queryRaw: mockQueryRaw,
      }),
  );
});

describe("generateRawToken + hashToken", () => {
  it("produces a long base64url token", () => {
    const t = generateRawToken();
    expect(t.length).toBeGreaterThanOrEqual(40);
    expect(t).toMatch(/^[A-Za-z0-9_-]+$/);
  });

  it("every generate call produces a distinct token", () => {
    const a = generateRawToken();
    const b = generateRawToken();
    expect(a).not.toBe(b);
  });

  it("hashToken is deterministic + 64 hex chars", () => {
    const raw = "abc123";
    const a = hashToken(raw);
    const b = hashToken(raw);
    expect(a).toBe(b);
    expect(a).toHaveLength(64);
    expect(a).toMatch(/^[0-9a-f]+$/);
  });

  it("hashToken differs for different inputs", () => {
    expect(hashToken("a")).not.toBe(hashToken("b"));
  });
});

describe("createAuthToken", () => {
  it("invalidates prior unused tokens by default", async () => {
    mockUpdateMany.mockResolvedValueOnce({ count: 2 });
    mockCreate.mockResolvedValueOnce({ id: "tk1" });

    await createAuthToken({
      userId: "u1",
      purpose: "PASSWORD_RESET",
      expiresInMs: 60_000,
      expectedUserEmail: "synthetic@example.test",
    });

    expect(mockUpdateMany).toHaveBeenCalledTimes(1);
    expect(mockUpdateMany.mock.calls[0][0].where).toMatchObject({
      userId: "u1",
      purpose: "PASSWORD_RESET",
      usedAt: null,
    });
  });

  it("serializes minting under the canonical user lock", async () => {
    mockUpdateMany.mockResolvedValueOnce({ count: 0 });
    mockCreate.mockResolvedValueOnce({ id: "tk1" });

    await createAuthToken({
      userId: "u1",
      purpose: "EMAIL_VERIFICATION",
      expiresInMs: 60_000,
    });

    expect(mockTransaction).toHaveBeenCalledTimes(1);
    expect(mockQueryRaw).toHaveBeenCalledTimes(1);
    expect(mockUpdateMany).toHaveBeenCalledTimes(1);
    expect(mockCreate).toHaveBeenCalledTimes(1);
  });

  it("hashes the token before persisting it", async () => {
    mockUpdateMany.mockResolvedValueOnce({ count: 0 });
    mockCreate.mockResolvedValueOnce({ id: "tk1" });

    const { token, userEmail } = await createAuthToken({
      userId: "u1",
      purpose: "PASSWORD_RESET",
      expiresInMs: 60_000,
      expectedUserEmail: "synthetic@example.test",
    });

    const createArgs = mockCreate.mock.calls[0][0];
    // The plaintext token never enters the DB payload.
    expect(createArgs.data.tokenHash).toBe(hashToken(token));
    expect(createArgs.data.tokenHash).not.toBe(token);
    expect(createArgs.data.metadata).toEqual({
      email: "synthetic@example.test",
    });
    expect(userEmail).toBe("synthetic@example.test");
  });

  it("stores metadata when provided", async () => {
    mockUpdateMany.mockResolvedValueOnce({ count: 0 });
    mockCreate.mockResolvedValueOnce({ id: "tk1" });

    await createAuthToken({
      userId: "u1",
      purpose: "EMAIL_CHANGE",
      expiresInMs: 60_000,
      metadata: { newEmail: "new@example.com" },
    });

    const createArgs = mockCreate.mock.calls[0][0];
    expect(createArgs.data.metadata).toEqual({ newEmail: "new@example.com" });
  });

  it("leaves metadata undefined when omitted", async () => {
    mockUpdateMany.mockResolvedValueOnce({ count: 0 });
    mockCreate.mockResolvedValueOnce({ id: "tk1" });

    await createAuthToken({
      userId: "u1",
      purpose: "EMAIL_VERIFICATION",
      expiresInMs: 60_000,
    });

    const createArgs = mockCreate.mock.calls[0][0];
    expect(createArgs.data.metadata).toBeUndefined();
  });

  it("rejects password-reset minting without an exact normalized email binding", async () => {
    await expect(
      createAuthToken({
        userId: "u1",
        purpose: "PASSWORD_RESET",
        expiresInMs: 60_000,
      }),
    ).rejects.toBeInstanceOf(AuthTokenAuthorityError);
    await expect(
      createAuthToken({
        userId: "u1",
        purpose: "PASSWORD_RESET",
        expiresInMs: 60_000,
        expectedUserEmail: " Synthetic@Example.Test ",
      }),
    ).rejects.toBeInstanceOf(AuthTokenAuthorityError);

    expect(mockQueryRaw).not.toHaveBeenCalled();
    expect(mockUpdateMany).not.toHaveBeenCalled();
    expect(mockCreate).not.toHaveBeenCalled();
  });

  it("rejects a stale expected email under the canonical user lock", async () => {
    await expect(
      createAuthToken({
        userId: "u1",
        purpose: "PASSWORD_RESET",
        expiresInMs: 60_000,
        expectedUserEmail: "stale@example.test",
      }),
    ).rejects.toBeInstanceOf(AuthTokenAuthorityError);

    expect(mockQueryRaw).toHaveBeenCalledTimes(1);
    expect(mockUpdateMany).not.toHaveBeenCalled();
    expect(mockCreate).not.toHaveBeenCalled();
  });

  it("rejects minting for an inactive account under the user lock", async () => {
    mockQueryRaw.mockResolvedValueOnce([{ ...LOCKED_USER, isActive: false }]);

    await expect(
      createAuthToken({
        userId: "u1",
        purpose: "PASSWORD_RESET",
        expiresInMs: 60_000,
        expectedUserEmail: "synthetic@example.test",
      }),
    ).rejects.toBeInstanceOf(AuthTokenAuthorityError);

    expect(mockUpdateMany).not.toHaveBeenCalled();
    expect(mockCreate).not.toHaveBeenCalled();
  });
});

describe("consumeAuthToken", () => {
  const HASH_OF_VALID = hashToken("valid-token-value-must-be-20-plus-chars");

  function okRow(overrides: Record<string, unknown> = {}) {
    return {
      id: "tk1",
      userId: "u1",
      tokenHash: HASH_OF_VALID,
      purpose: "PASSWORD_RESET",
      expiresAt: new Date(Date.now() + 10_000),
      usedAt: null,
      metadata: { email: "synthetic@example.test" },
      ...overrides,
    };
  }

  it("returns ConsumedAuthToken on happy path", async () => {
    mockFindUnique.mockResolvedValue(okRow());
    mockUpdateMany.mockResolvedValueOnce({ count: 1 });

    const result = await consumeAuthToken({
      token: "valid-token-value-must-be-20-plus-chars",
      purpose: "PASSWORD_RESET",
    });

    expect(result).toEqual({
      id: "tk1",
      userId: "u1",
      metadata: { email: "synthetic@example.test" },
    });
    expect(mockFindUnique.mock.calls[0][0].where).toEqual({
      tokenHash: HASH_OF_VALID,
    });
  });

  it("returns null for too-short token without hitting DB", async () => {
    const result = await consumeAuthToken({
      token: "short",
      purpose: "PASSWORD_RESET",
    });
    expect(result).toBeNull();
    expect(mockFindUnique).not.toHaveBeenCalled();
  });

  it("returns null when row missing", async () => {
    mockFindUnique.mockResolvedValueOnce(null);
    const result = await consumeAuthToken({
      token: "valid-token-value-must-be-20-plus-chars",
      purpose: "PASSWORD_RESET",
    });
    expect(result).toBeNull();
    expect(mockUpdateMany).not.toHaveBeenCalled();
  });

  it("returns null on purpose mismatch", async () => {
    mockFindUnique.mockResolvedValue(okRow({ purpose: "EMAIL_CHANGE" }));
    const result = await consumeAuthToken({
      token: "valid-token-value-must-be-20-plus-chars",
      purpose: "PASSWORD_RESET",
    });
    expect(result).toBeNull();
    expect(mockUpdateMany).not.toHaveBeenCalled();
  });

  it("returns null when token already used", async () => {
    mockFindUnique.mockResolvedValue(okRow({ usedAt: new Date() }));
    const result = await consumeAuthToken({
      token: "valid-token-value-must-be-20-plus-chars",
      purpose: "PASSWORD_RESET",
    });
    expect(result).toBeNull();
    expect(mockUpdateMany).not.toHaveBeenCalled();
  });

  it("returns null when expired", async () => {
    mockFindUnique.mockResolvedValue(
      okRow({ expiresAt: new Date(Date.now() - 1) }),
    );
    const result = await consumeAuthToken({
      token: "valid-token-value-must-be-20-plus-chars",
      purpose: "PASSWORD_RESET",
    });
    expect(result).toBeNull();
    expect(mockUpdateMany).not.toHaveBeenCalled();
  });

  it("returns null when the atomic mark-used race is lost", async () => {
    mockFindUnique.mockResolvedValue(okRow());
    mockUpdateMany.mockResolvedValueOnce({ count: 0 });
    const result = await consumeAuthToken({
      token: "valid-token-value-must-be-20-plus-chars",
      purpose: "PASSWORD_RESET",
    });
    expect(result).toBeNull();
  });

  it.each([
    ["missing", null],
    ["stale", { email: "stale@example.test" }],
  ])(
    "returns null when password-reset email metadata is %s",
    async (_label, metadata) => {
      mockFindUnique.mockResolvedValue(okRow({ metadata }));
      const result = await consumeAuthToken({
        token: "valid-token-value-must-be-20-plus-chars",
        purpose: "PASSWORD_RESET",
      });

      expect(result).toBeNull();
      expect(mockUpdateMany).not.toHaveBeenCalled();
    },
  );

  it("forwards metadata on happy path", async () => {
    mockFindUnique.mockResolvedValue(
      okRow({
        purpose: "EMAIL_CHANGE",
        metadata: { newEmail: "new@example.com" },
      }),
    );
    mockUpdateMany.mockResolvedValueOnce({ count: 1 });

    const result = await consumeAuthToken({
      token: "valid-token-value-must-be-20-plus-chars",
      purpose: "EMAIL_CHANGE",
    });

    expect(result).toEqual({
      id: "tk1",
      userId: "u1",
      metadata: { newEmail: "new@example.com" },
    });
  });
});

describe("invalidateAuthTokens", () => {
  it("updates all unused tokens for a (user, purpose) pair", async () => {
    mockUpdateMany.mockResolvedValueOnce({ count: 3 });
    await invalidateAuthTokens("u1", "PASSWORD_RESET");
    expect(mockUpdateMany).toHaveBeenCalledWith({
      where: { userId: "u1", purpose: "PASSWORD_RESET", usedAt: null },
      data: expect.objectContaining({ usedAt: expect.any(Date) }),
    });
  });
});
