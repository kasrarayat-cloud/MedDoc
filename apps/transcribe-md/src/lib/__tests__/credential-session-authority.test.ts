import { describe, expect, it, vi } from "vitest";

import {
  CredentialSessionAuthorityError,
  finalizeCredentialSession,
  recordCredentialFailure,
  type CredentialUserSnapshot,
} from "../credential-session-authority";

const NOW = new Date("2026-07-20T12:00:00.000Z");

function snapshot(
  overrides: Partial<CredentialUserSnapshot> = {},
): CredentialUserSnapshot {
  return {
    id: "doctor-synthetic",
    email: "doctor@synthetic.invalid",
    name: "Synthetic Doctor",
    practiceId: "practice-synthetic",
    passwordHash: "hash-current",
    role: "DOCTOR",
    products: ["TRANSCRIBE_MD"],
    emailVerified: new Date("2026-07-20T10:00:00.000Z"),
    mfaEnabled: true,
    mfaSecret: "secret-current",
    mfaVerifiedAt: new Date("2026-07-20T10:00:00.000Z"),
    mfaBackupCodes: ["recovery-current", "recovery-next"],
    ...overrides,
  };
}

function currentUser(
  source: CredentialUserSnapshot = snapshot(),
  overrides: Record<string, unknown> = {},
) {
  return {
    ...source,
    products: [...source.products],
    mfaBackupCodes: [...source.mfaBackupCodes],
    isActive: true,
    deactivatedAt: null,
    suspendedAt: null,
    softDeletedAt: null,
    lockedUntil: null,
    failedLoginCount: 0,
    ...overrides,
  };
}

function transaction(
  options: {
    source?: CredentialUserSnapshot;
    user?: ReturnType<typeof currentUser>;
    practice?: { id: string; isActive: boolean } | null;
  } = {},
) {
  const source = options.source ?? snapshot();
  const user = options.user ?? currentUser(source);
  const session = {
    id: "session-row",
    userId: source.id,
    sessionToken: "session-synthetic-current",
  };
  return {
    $queryRaw: vi
      .fn()
      .mockResolvedValueOnce([{ id: source.practiceId }])
      .mockResolvedValueOnce([{ id: source.id }]),
    practice: {
      findUnique: vi
        .fn()
        .mockResolvedValue(
          options.practice === undefined
            ? { id: source.practiceId, isActive: true }
            : options.practice,
        ),
    },
    user: {
      findUnique: vi.fn().mockResolvedValue(user),
      update: vi.fn().mockResolvedValue(user),
    },
    userSession: {
      deleteMany: vi.fn().mockResolvedValue({ count: 2 }),
      create: vi.fn().mockResolvedValue(session),
    },
    auditLog: {
      create: vi.fn().mockResolvedValue({ id: "audit-synthetic" }),
    },
  };
}

function finalizeInput(source = snapshot()) {
  return {
    snapshot: source,
    surface: "physician" as const,
    secondFactor: {
      kind: "recovery" as const,
      matchedHash: "recovery-current",
    },
    requireVerifiedEmail: true,
    sessionToken: "session-synthetic-current",
    now: NOW,
  };
}

describe("credential-session final authority", () => {
  it("consumes the proved recovery code and issues one session atomically", async () => {
    const source = snapshot();
    const tx = transaction({ source });

    await expect(
      finalizeCredentialSession(tx as never, finalizeInput(source)),
    ).resolves.toMatchObject({ session: { id: "session-row" } });
    expect(tx.$queryRaw).toHaveBeenCalledTimes(2);
    expect(tx.user.update).toHaveBeenCalledWith({
      where: { id: source.id },
      data: {
        lastLogin: NOW,
        failedLoginCount: 0,
        lockedUntil: null,
        mfaBackupCodes: ["recovery-next"],
      },
    });
    expect(tx.userSession.deleteMany).toHaveBeenCalledWith({
      where: { userId: source.id },
    });
    expect(tx.userSession.create).toHaveBeenCalledWith({
      data: expect.objectContaining({
        userId: source.id,
        sessionToken: "session-synthetic-current",
      }),
    });
    expect(tx.auditLog.create).toHaveBeenNthCalledWith(1, {
      data: expect.objectContaining({
        action: "MFA_CHALLENGE_PASSED",
        userId: source.id,
        practiceId: source.practiceId,
        success: true,
      }),
    });
    expect(tx.auditLog.create).toHaveBeenNthCalledWith(2, {
      data: expect.objectContaining({
        action: "LOGIN_SUCCESS",
        userId: source.id,
        practiceId: source.practiceId,
        success: true,
      }),
    });
    expect(tx.auditLog.create.mock.invocationCallOrder[1]).toBeLessThan(
      tx.userSession.create.mock.invocationCallOrder[0]!,
    );
  });

  it("fails issuance closed when its required success audit cannot commit", async () => {
    const source = snapshot();
    const tx = transaction({ source });
    tx.auditLog.create
      .mockResolvedValueOnce({ id: "mfa-audit-synthetic" })
      .mockRejectedValueOnce(new Error("synthetic audit outage"));

    await expect(
      finalizeCredentialSession(tx as never, finalizeInput(source)),
    ).rejects.toThrow("synthetic audit outage");
    expect(tx.auditLog.create).toHaveBeenCalledTimes(2);
    expect(tx.userSession.create).not.toHaveBeenCalled();
  });

  it("requires one transactional login receipt without MFA", async () => {
    const source = snapshot({
      mfaEnabled: false,
      mfaSecret: null,
      mfaVerifiedAt: null,
      mfaBackupCodes: [],
    });
    const tx = transaction({ source });

    await finalizeCredentialSession(tx as never, {
      ...finalizeInput(source),
      secondFactor: { kind: "none" },
    });

    expect(tx.auditLog.create).toHaveBeenCalledTimes(1);
    expect(tx.auditLog.create).toHaveBeenCalledWith({
      data: expect.objectContaining({ action: "LOGIN_SUCCESS" }),
    });
  });

  it.each([
    ["password replacement", { passwordHash: "hash-rotated" }],
    ["MFA secret rotation", { mfaSecret: "secret-rotated" }],
    ["recovery replacement", { mfaBackupCodes: ["recovery-rotated"] }],
    ["tenant transfer", { practiceId: "practice-other" }],
    ["suspension", { suspendedAt: NOW }],
  ])("denies %s without issuing a session", async (_label, changed) => {
    const source = snapshot();
    const tx = transaction({
      source,
      user: currentUser(source, changed),
    });

    await expect(
      finalizeCredentialSession(tx as never, finalizeInput(source)),
    ).rejects.toBeInstanceOf(CredentialSessionAuthorityError);
    expect(tx.user.update).not.toHaveBeenCalled();
    expect(tx.userSession.create).not.toHaveBeenCalled();
  });

  it("denies an inactive practice without issuing a session", async () => {
    const source = snapshot();
    const tx = transaction({
      source,
      practice: { id: source.practiceId, isActive: false },
    });

    await expect(
      finalizeCredentialSession(tx as never, finalizeInput(source)),
    ).rejects.toBeInstanceOf(CredentialSessionAuthorityError);
    expect(tx.userSession.create).not.toHaveBeenCalled();
  });

  it("requires an exact current recovery-code hash", async () => {
    const source = snapshot();
    const tx = transaction({ source });

    await expect(
      finalizeCredentialSession(tx as never, {
        ...finalizeInput(source),
        secondFactor: { kind: "recovery", matchedHash: "not-current" },
      }),
    ).rejects.toBeInstanceOf(CredentialSessionAuthorityError);
    expect(tx.userSession.create).not.toHaveBeenCalled();
  });

  it("denies an unverified account when the caller requires verification", async () => {
    const source = snapshot({ emailVerified: null });
    const tx = transaction({ source });

    await expect(
      finalizeCredentialSession(tx as never, finalizeInput(source)),
    ).rejects.toBeInstanceOf(CredentialSessionAuthorityError);
    expect(tx.user.update).not.toHaveBeenCalled();
    expect(tx.userSession.create).not.toHaveBeenCalled();
  });
});

describe("credential-failure thresholding", () => {
  it("locks exactly on the fifth serialized current failure", async () => {
    const source = snapshot();
    const tx = transaction({
      source,
      user: currentUser(source, { failedLoginCount: 4 }),
    });

    await expect(
      recordCredentialFailure(tx as never, {
        snapshot: source,
        surface: "physician",
        now: NOW,
      }),
    ).resolves.toEqual({ recorded: true, locked: true, failedLoginCount: 5 });
    expect(tx.user.update).toHaveBeenCalledWith({
      where: { id: source.id },
      data: {
        failedLoginCount: 5,
        lockedUntil: new Date("2026-07-20T12:15:00.000Z"),
      },
    });
  });

  it("does not advance an active lock", async () => {
    const source = snapshot();
    const tx = transaction({
      source,
      user: currentUser(source, {
        failedLoginCount: 5,
        lockedUntil: new Date("2026-07-20T12:10:00.000Z"),
      }),
    });

    await expect(
      recordCredentialFailure(tx as never, {
        snapshot: source,
        surface: "physician",
        now: NOW,
      }),
    ).resolves.toEqual({ recorded: false, locked: true, failedLoginCount: 5 });
    expect(tx.user.update).not.toHaveBeenCalled();
  });

  it("starts a fresh count after an expired lock", async () => {
    const source = snapshot();
    const tx = transaction({
      source,
      user: currentUser(source, {
        failedLoginCount: 5,
        lockedUntil: new Date("2026-07-20T11:59:59.000Z"),
      }),
    });

    await expect(
      recordCredentialFailure(tx as never, {
        snapshot: source,
        surface: "physician",
        now: NOW,
      }),
    ).resolves.toEqual({ recorded: true, locked: false, failedLoginCount: 1 });
  });
});
