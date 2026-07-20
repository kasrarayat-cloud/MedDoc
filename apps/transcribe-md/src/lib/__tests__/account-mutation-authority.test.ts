import { describe, expect, it, vi } from "vitest";

import {
  AccountMutationAuthorityError,
  lockCurrentAccountMutationAuthority,
} from "../account-mutation-authority";

const NOW = new Date("2026-07-20T12:00:00.000Z");

function currentUser(overrides: Record<string, unknown> = {}) {
  return {
    id: "doctor-synthetic",
    email: "doctor@synthetic.invalid",
    name: "Synthetic Doctor",
    passwordHash: "hash-current",
    role: "DOCTOR",
    products: ["TRANSCRIBE_MD"],
    practiceId: "practice-synthetic",
    isActive: true,
    deactivatedAt: null,
    suspendedAt: null,
    softDeletedAt: null,
    forceLogoutAt: null,
    mfaEnabled: true,
    mfaSecret: "secret-current",
    mfaVerifiedAt: new Date("2026-07-20T10:00:00.000Z"),
    mfaBackupCodes: ["recovery-current"],
    ...overrides,
  };
}

function currentSession(overrides: Record<string, unknown> = {}) {
  return {
    userId: "doctor-synthetic",
    createdAt: new Date("2026-07-20T10:00:00.000Z"),
    expiresAt: new Date("2026-07-21T10:00:00.000Z"),
    ...overrides,
  };
}

function transaction(
  user = currentUser(),
  session: ReturnType<typeof currentSession> | null = currentSession(),
  practice: { id: string; isActive: boolean } | null = {
    id: "practice-synthetic",
    isActive: true,
  },
) {
  const queryRaw = vi
    .fn()
    .mockResolvedValueOnce([{ pg_advisory_xact_lock: null }])
    .mockResolvedValueOnce([{ id: "practice-synthetic" }])
    .mockResolvedValueOnce([{ id: "doctor-synthetic" }])
    .mockResolvedValueOnce(session ? [{ id: "session-row" }] : []);
  return {
    $queryRaw: queryRaw,
    user: { findUnique: vi.fn().mockResolvedValue(user) },
    practice: {
      findUnique: vi.fn().mockResolvedValue(practice),
    },
    userSession: { findUnique: vi.fn().mockResolvedValue(session) },
  };
}

const baseInput = {
  userId: "doctor-synthetic",
  sessionId: "session-synthetic",
  expectedPracticeId: "practice-synthetic",
  expectedPasswordHash: "hash-current",
  surface: "physician" as const,
  now: NOW,
};

describe("final account-mutation authority", () => {
  it("returns the locked current physician and exact session", async () => {
    const tx = transaction();
    await expect(
      lockCurrentAccountMutationAuthority(tx as never, baseInput),
    ).resolves.toMatchObject({
      user: { id: "doctor-synthetic", practiceId: "practice-synthetic" },
      session: { userId: "doctor-synthetic" },
    });
    expect(tx.$queryRaw).toHaveBeenCalledTimes(4);
  });

  it.each([
    ["revoked session", currentUser(), null],
    [
      "force logout",
      currentUser({ forceLogoutAt: new Date("2026-07-20T10:00:00.000Z") }),
      currentSession(),
    ],
    [
      "tenant transfer",
      currentUser({ practiceId: "practice-other" }),
      currentSession(),
    ],
    ["role change", currentUser({ role: "STAFF" }), currentSession()],
    ["product revocation", currentUser({ products: [] }), currentSession()],
    [
      "password change",
      currentUser({ passwordHash: "hash-new" }),
      currentSession(),
    ],
    ["suspension", currentUser({ suspendedAt: NOW }), currentSession()],
  ])("denies %s at the final lock", async (_label, user, session) => {
    await expect(
      lockCurrentAccountMutationAuthority(
        transaction(user, session) as never,
        baseInput,
      ),
    ).rejects.toBeInstanceOf(AccountMutationAuthorityError);
  });

  it("admits only a fresh current platform-admin entitlement", async () => {
    const admin = currentUser({
      role: "DOCTOR",
      products: ["SUPER_ADMIN"],
    });
    await expect(
      lockCurrentAccountMutationAuthority(transaction(admin) as never, {
        ...baseInput,
        surface: "platform-admin",
      }),
    ).resolves.toMatchObject({ user: { products: ["SUPER_ADMIN"] } });

    const stale = currentSession({
      createdAt: new Date("2026-07-20T00:00:00.000Z"),
    });
    await expect(
      lockCurrentAccountMutationAuthority(transaction(admin, stale) as never, {
        ...baseInput,
        surface: "platform-admin",
      }),
    ).rejects.toBeInstanceOf(AccountMutationAuthorityError);
  });

  it("denies an inactive practice at the final lock", async () => {
    await expect(
      lockCurrentAccountMutationAuthority(
        transaction(currentUser(), currentSession(), {
          id: "practice-synthetic",
          isActive: false,
        }) as never,
        baseInput,
      ),
    ).rejects.toBeInstanceOf(AccountMutationAuthorityError);
  });

  it("requires complete current MFA for platform-admin mutations by default", async () => {
    const incompleteAdmin = currentUser({
      products: ["SUPER_ADMIN"],
      mfaEnabled: false,
      mfaSecret: null,
      mfaVerifiedAt: null,
      mfaBackupCodes: [],
    });

    await expect(
      lockCurrentAccountMutationAuthority(
        transaction(incompleteAdmin) as never,
        {
          ...baseInput,
          surface: "platform-admin",
        },
      ),
    ).rejects.toBeInstanceOf(AccountMutationAuthorityError);

    await expect(
      lockCurrentAccountMutationAuthority(
        transaction(incompleteAdmin) as never,
        {
          ...baseInput,
          surface: "platform-admin",
          requireMfa: false,
        },
      ),
    ).resolves.toMatchObject({ user: { products: ["SUPER_ADMIN"] } });
  });
});
