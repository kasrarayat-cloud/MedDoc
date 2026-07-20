import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findSession: vi.fn(),
  deleteSessions: vi.fn(),
  createSession: vi.fn(),
  updateSession: vi.fn(),
  lockUser: vi.fn(),
  transaction: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    $transaction: mocks.transaction,
    userSession: {
      findUnique: mocks.findSession,
      deleteMany: mocks.deleteSessions,
      create: mocks.createSession,
      updateMany: mocks.updateSession,
    },
  },
}));

import {
  recordSessionLogin,
  revokeAllUserSessionsFromCurrentSession,
  validateSession,
  type RevokeAllUserSessionsFromCurrentSessionInput,
  type ValidateSessionInput,
} from "./user-session";

const NOW = new Date("2026-07-20T12:00:00.000Z");
const CREATED_AT = new Date("2026-07-20T10:00:00.000Z");

interface SessionRowOverrides {
  row?: Record<string, unknown>;
  user?: Record<string, unknown>;
  practice?: Record<string, unknown>;
}

function currentSession(overrides: SessionRowOverrides = {}) {
  const practice = {
    id: "practice-current",
    isActive: true,
    ...overrides.practice,
  };
  const user = {
    id: "doctor-current",
    email: "current-doctor@synthetic.test",
    name: "Current Synthetic Doctor",
    role: "DOCTOR",
    practiceId: "practice-current",
    products: ["TRANSCRIBE_MD"],
    isActive: true,
    deactivatedAt: null,
    suspendedAt: null,
    softDeletedAt: null,
    forceLogoutAt: null,
    practice,
    ...overrides.user,
  };
  return {
    id: "session-row-current",
    userId: "doctor-current",
    createdAt: CREATED_AT,
    expiresAt: new Date("2026-07-21T10:00:00.000Z"),
    user,
    ...overrides.row,
  };
}

function validationInput(
  overrides: Partial<ValidateSessionInput> = {},
): ValidateSessionInput {
  return {
    sessionToken: "session-current",
    expectedUserId: "doctor-current",
    expectedPracticeId: "practice-current",
    allowedRoles: ["DOCTOR"],
    requiredProducts: ["TRANSCRIBE_MD"],
    now: NOW,
    ...overrides,
  };
}

function revocationInput(
  overrides: Partial<RevokeAllUserSessionsFromCurrentSessionInput> = {},
): RevokeAllUserSessionsFromCurrentSessionInput {
  return {
    sessionToken: "session-current",
    userId: "doctor-current",
    now: NOW,
    ...overrides,
  };
}

function lockedPractice(overrides: Record<string, unknown> = {}) {
  return [{ id: "practice-current", isActive: true, ...overrides }];
}

function lockedUser(overrides: Record<string, unknown> = {}) {
  return [
    {
      id: "doctor-current",
      practiceId: "practice-current",
      isActive: true,
      deactivatedAt: null,
      suspendedAt: null,
      softDeletedAt: null,
      forceLogoutAt: null,
      ...overrides,
    },
  ];
}

function lockedSession(overrides: Record<string, unknown> = {}) {
  return [
    {
      id: "session-row-current",
      userId: "doctor-current",
      createdAt: CREATED_AT,
      expiresAt: new Date("2026-07-21T10:00:00.000Z"),
      ...overrides,
    },
  ];
}

function rawSql(call: unknown[] | undefined): string {
  return Array.from((call?.[0] ?? []) as readonly string[]).join("?");
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.findSession.mockResolvedValue(currentSession());
  mocks.deleteSessions.mockResolvedValue({ count: 1 });
  mocks.createSession.mockResolvedValue({ id: "session-row-new" });
  mocks.updateSession.mockResolvedValue({ id: "session-row-current" });
  mocks.lockUser.mockResolvedValue([{ id: "doctor-current" }]);
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        $queryRaw: mocks.lockUser,
        userSession: {
          deleteMany: mocks.deleteSessions,
          create: mocks.createSession,
        },
      }),
  );
});

describe("single-current-session login serialization", () => {
  it("locks the canonical user before revoking and creating a session", async () => {
    await expect(
      recordSessionLogin({
        userId: "doctor-current",
        sessionToken: "session-new",
        ttlMs: 60_000,
      }),
    ).resolves.toEqual({ id: "session-row-new" });

    expect(mocks.lockUser).toHaveBeenCalledOnce();
    expect(mocks.lockUser.mock.calls[0]?.[1]).toBe("doctor-current");
    expect(mocks.lockUser.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.deleteSessions.mock.invocationCallOrder[0]!,
    );
    expect(mocks.deleteSessions.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.createSession.mock.invocationCallOrder[0]!,
    );
    expect(mocks.deleteSessions).toHaveBeenCalledWith({
      where: { userId: "doctor-current" },
    });
    expect(mocks.createSession).toHaveBeenCalledWith({
      data: expect.objectContaining({
        userId: "doctor-current",
        sessionToken: "session-new",
      }),
    });
  });

  it("fails closed without deleting sessions when the current user cannot be locked", async () => {
    mocks.lockUser.mockResolvedValue([]);

    await expect(
      recordSessionLogin({
        userId: "doctor-missing",
        sessionToken: "session-new",
      }),
    ).rejects.toThrow("Unable to establish current session authority.");
    expect(mocks.deleteSessions).not.toHaveBeenCalled();
    expect(mocks.createSession).not.toHaveBeenCalled();
  });
});

describe("atomic all-device session revocation", () => {
  it("locks exact current lifecycle authority before deleting every user session", async () => {
    mocks.lockUser
      .mockResolvedValueOnce(lockedPractice())
      .mockResolvedValueOnce(lockedUser())
      .mockResolvedValueOnce(lockedSession());

    await expect(
      revokeAllUserSessionsFromCurrentSession(revocationInput()),
    ).resolves.toBe(true);

    expect(mocks.lockUser).toHaveBeenCalledTimes(3);
    expect(rawSql(mocks.lockUser.mock.calls[0])).toContain(
      'FROM "practices" practice',
    );
    expect(rawSql(mocks.lockUser.mock.calls[0])).toContain(
      "FOR UPDATE OF practice",
    );
    expect(rawSql(mocks.lockUser.mock.calls[1])).toContain('FROM "users"');
    expect(rawSql(mocks.lockUser.mock.calls[1])).toContain("FOR UPDATE");
    expect(rawSql(mocks.lockUser.mock.calls[2])).toContain(
      'FROM "user_sessions"',
    );
    expect(rawSql(mocks.lockUser.mock.calls[2])).toContain(
      '"sessionToken" = ?',
    );
    expect(mocks.lockUser.mock.calls[2]?.[1]).toBe("doctor-current");
    expect(mocks.lockUser.mock.calls[2]?.[2]).toBe("session-current");
    expect(mocks.lockUser.mock.invocationCallOrder[2]).toBeLessThan(
      mocks.deleteSessions.mock.invocationCallOrder[0]!,
    );
    expect(mocks.deleteSessions).toHaveBeenCalledWith({
      where: { userId: "doctor-current" },
    });
  });

  it("denies a stale signed cookie without deleting the newer user session", async () => {
    mocks.lockUser
      .mockResolvedValueOnce(lockedPractice())
      .mockResolvedValueOnce(lockedUser())
      // The stale JWT's exact token was removed by the newer login. A newer
      // row may exist for this user, but it is deliberately not selected.
      .mockResolvedValueOnce([]);

    await expect(
      revokeAllUserSessionsFromCurrentSession(
        revocationInput({ sessionToken: "session-stale-signed" }),
      ),
    ).resolves.toBe(false);

    expect(mocks.lockUser.mock.calls[2]?.[1]).toBe("doctor-current");
    expect(mocks.lockUser.mock.calls[2]?.[2]).toBe("session-stale-signed");
    expect(mocks.deleteSessions).not.toHaveBeenCalled();
  });

  it.each([
    ["inactive practice", lockedPractice({ isActive: false }), null, null],
    [
      "transferred user",
      lockedPractice(),
      lockedUser({ practiceId: "practice-new" }),
      null,
    ],
    [
      "suspended user",
      lockedPractice(),
      lockedUser({ suspendedAt: NOW }),
      null,
    ],
    [
      "expired exact session",
      lockedPractice(),
      lockedUser(),
      lockedSession({ expiresAt: NOW }),
    ],
    [
      "force-logout epoch",
      lockedPractice(),
      lockedUser({ forceLogoutAt: CREATED_AT }),
      lockedSession(),
    ],
  ] satisfies ReadonlyArray<
    readonly [
      string,
      Array<Record<string, unknown>>,
      Array<Record<string, unknown>> | null,
      Array<Record<string, unknown>> | null,
    ]
  >)("denies %s before deletion", async (_label, practice, user, session) => {
    mocks.lockUser.mockResolvedValueOnce(practice);
    if (user) mocks.lockUser.mockResolvedValueOnce(user);
    if (session) mocks.lockUser.mockResolvedValueOnce(session);

    await expect(
      revokeAllUserSessionsFromCurrentSession(revocationInput()),
    ).resolves.toBe(false);
    expect(mocks.deleteSessions).not.toHaveBeenCalled();
  });

  it("rejects incomplete bindings without opening a transaction", async () => {
    await expect(
      revokeAllUserSessionsFromCurrentSession(
        revocationInput({ sessionToken: "" }),
      ),
    ).resolves.toBe(false);
    await expect(
      revokeAllUserSessionsFromCurrentSession(revocationInput({ userId: "" })),
    ).resolves.toBe(false);
    expect(mocks.transaction).not.toHaveBeenCalled();
  });
});

describe("current database-backed user session validation", () => {
  it("returns the current identity and refreshes mutable profile claims", async () => {
    await expect(validateSession(validationInput())).resolves.toMatchObject({
      user: {
        id: "doctor-current",
        email: "current-doctor@synthetic.test",
        name: "Current Synthetic Doctor",
        role: "DOCTOR",
        practiceId: "practice-current",
      },
    });
    expect(mocks.findSession).toHaveBeenCalledWith({
      where: { sessionToken: "session-current" },
      select: {
        id: true,
        userId: true,
        createdAt: true,
        expiresAt: true,
        user: {
          select: {
            id: true,
            email: true,
            name: true,
            role: true,
            practiceId: true,
            products: true,
            isActive: true,
            deactivatedAt: true,
            suspendedAt: true,
            softDeletedAt: true,
            forceLogoutAt: true,
            practice: { select: { id: true, isActive: true } },
          },
        },
      },
    });
    expect(mocks.updateSession).toHaveBeenCalledWith({
      where: {
        id: "session-row-current",
        userId: "doctor-current",
        sessionToken: "session-current",
      },
      data: { lastActiveAt: NOW },
    });
  });

  it("never logs database-driver credential material when the activity touch fails", async () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    mocks.updateSession.mockRejectedValue(
      new Error(
        "synthetic driver failure at postgresql://user:synthetic-secret@db.invalid/auth",
      ),
    );

    await expect(validateSession(validationInput())).resolves.not.toBeNull();
    await Promise.resolve();
    await Promise.resolve();

    expect(consoleError).toHaveBeenCalledWith(
      "[auth] UserSession.lastActiveAt touch failed",
    );
    expect(JSON.stringify(consoleError.mock.calls)).not.toContain(
      "synthetic-secret",
    );
    consoleError.mockRestore();
  });

  it.each([
    ["inactive user", { user: { isActive: false } }],
    [
      "deactivated user",
      { user: { deactivatedAt: new Date("2026-07-20T11:00:00.000Z") } },
    ],
    [
      "suspended user",
      { user: { suspendedAt: new Date("2026-07-20T11:00:00.000Z") } },
    ],
    [
      "soft-deleted user",
      { user: { softDeletedAt: new Date("2026-07-20T11:00:00.000Z") } },
    ],
    ["demoted user", { user: { role: "STAFF" } }],
    ["removed product", { user: { products: ["MEDDOC_PRO"] } }],
    ["inactive practice", { practice: { isActive: false } }],
    [
      "practice transfer",
      {
        user: { practiceId: "practice-transferred" },
        practice: { id: "practice-transferred" },
      },
    ],
    [
      "force-logout epoch at session creation",
      { user: { forceLogoutAt: CREATED_AT } },
    ],
    ["session/user mismatch", { row: { userId: "doctor-foreign" } }],
  ] satisfies ReadonlyArray<readonly [string, SessionRowOverrides]>)(
    "rejects a validly signed JWT after %s",
    async (_label, overrides) => {
      mocks.findSession.mockResolvedValue(currentSession(overrides));

      await expect(validateSession(validationInput())).resolves.toBeNull();
      expect(mocks.updateSession).not.toHaveBeenCalled();
    },
  );

  it("rejects missing exact JWT bindings before database access", async () => {
    await expect(
      validateSession(validationInput({ sessionToken: "" })),
    ).resolves.toBeNull();
    await expect(
      validateSession(validationInput({ expectedUserId: "" })),
    ).resolves.toBeNull();
    await expect(
      validateSession(validationInput({ expectedPracticeId: "" })),
    ).resolves.toBeNull();
    expect(mocks.findSession).not.toHaveBeenCalled();
  });

  it("rejects and cleans up an expired session", async () => {
    mocks.findSession.mockResolvedValue(
      currentSession({ row: { expiresAt: NOW } }),
    );

    await expect(validateSession(validationInput())).resolves.toBeNull();
    expect(mocks.deleteSessions).toHaveBeenCalledWith({
      where: { id: "session-row-current" },
    });
  });

  it("accepts either exact current grant in a disjunctive admin policy", async () => {
    const anyOf = [
      {
        allowedRoles: ["ADMIN", "SUPER_ADMIN"] as const,
        requiredProducts: ["TRANSCRIBE_MD"] as const,
      },
      { requiredProducts: ["SUPER_ADMIN"] as const },
    ];

    mocks.findSession.mockResolvedValue(
      currentSession({
        user: {
          role: "ADMIN",
          products: ["TRANSCRIBE_MD"],
        },
      }),
    );
    await expect(
      validateSession(
        validationInput({
          allowedRoles: undefined,
          requiredProducts: undefined,
          anyOf,
        }),
      ),
    ).resolves.not.toBeNull();

    mocks.findSession.mockResolvedValue(
      currentSession({
        user: { role: "DOCTOR", products: ["SUPER_ADMIN"] },
      }),
    );
    await expect(
      validateSession(
        validationInput({
          allowedRoles: undefined,
          requiredProducts: undefined,
          anyOf,
        }),
      ),
    ).resolves.not.toBeNull();
  });

  it("rejects an ordinary physician and an empty disjunctive policy", async () => {
    const ordinary = validationInput({
      allowedRoles: undefined,
      requiredProducts: undefined,
      anyOf: [
        {
          allowedRoles: ["ADMIN", "SUPER_ADMIN"],
          requiredProducts: ["TRANSCRIBE_MD"],
        },
        { requiredProducts: ["SUPER_ADMIN"] },
      ],
    });
    await expect(validateSession(ordinary)).resolves.toBeNull();

    await expect(
      validateSession({ ...ordinary, anyOf: [] }),
    ).resolves.toBeNull();
    expect(mocks.updateSession).not.toHaveBeenCalled();
  });
});
